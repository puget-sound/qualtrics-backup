import requests
import json
import zipfile
import StringIO
import smtplib

def survey():
    # Setting parameters
    #apiToken = "XXXXXTOKENHEREXXXXX"

    userUrl = 'https://co1.qualtrics.com/API/v3/users/'
    surveyUrl = 'https://co1.qualtrics.com/API/v3/surveys/'
    baseUrl = 'https://co1.qualtrics.com/API/v3/responseexports/'
    headers = {
        'content-type': "application/json",
        'x-api-token': apiToken,
    }

    newSurveyStatus = []

    # Grab the list of users
    usersRequestResponse = requests.get(userUrl, headers=headers)
    userResults = usersRequestResponse.json()['result']['elements']

    # Loop through users to get API tokens
    for user in userResults:
        print user['id']
        print user['username']

        tokenUrl = userUrl + user['id'] + '/apitoken'
        tokenRequestResponse = requests.get(tokenUrl, headers=headers)
        # If user has a token, get the token
        if tokenRequestResponse.status_code == 200:
            userToken = tokenRequestResponse.json()['result']['apiToken']
            print userToken
            userHeaders = {
                'content-type': "application/json",
                'x-api-token': userToken,
            }
            # Grab the list of surveys
            surveysRequestResponse = requests.get(surveyUrl, headers=userHeaders)
            if surveysRequestResponse.status_code != 200:
                print 'LIST OF SURVEYS retrieval fail'
                continue
            results = surveysRequestResponse.json()['result']['elements']
            resultsNextPage = surveysRequestResponse.json()['result']['nextPage']

            # Loop through surveys to download the export file
            def download_surveys(results):
                fileFormats = ['csv', 'xml']
                surveyStatus = []

                requestCheckProgress = 0
                requestCheckFile = None
                requestCheckStatus = 'in progress'

                # Load survey status file
                with open('qualtrics-status.json', 'r') as f:
                    surveyStatus = json.load(f)

                for result in results[:2]:
                    print result['id'] + ' -- ' + result['name'].encode('ascii', 'replace')
                    # Store new active status
                    thisStatus = {"id":result['id'], "isActive": result['isActive']}
                    newSurveyStatus.append(thisStatus)
                    #Grab the previous active status
                    wasActive = True
                    for survey in surveyStatus:
                        if survey['id'] == result['id']:
                            wasActive = survey['isActive']

                    # If the survey was inactive last time and inactive this time, don't download
                    if not result['isActive'] and not wasActive:
                        print 'not active'
                        continue
                    #Creating Data Export, one for CSV & one for XML
                    for fileFormat in fileFormats:
                        downloadRequestUrl = baseUrl
                        downloadRequestPayload = '{"format":"' + fileFormat + '","surveyId":"' + result['id'] + '"}'
                        downloadRequestResponse = requests.post(downloadRequestUrl, data=downloadRequestPayload, headers=userHeaders)
                        if downloadRequestResponse.status_code != 200:
                            print 'COULD NOT CREATE data export'
                            continue
                        progressId = downloadRequestResponse.json()['result']['id']
                        print progressId

                        # Checking on Data Export Progress and waiting until export is ready
                        # and a file exists
                        while (requestCheckProgress < 100 or requestCheckFile == None) and requestCheckStatus == 'in progress':
                            requestCheckUrl = baseUrl + progressId
                            requestCheckResponse = requests.get(requestCheckUrl, headers=userHeaders)
                            print requestCheckResponse.json()
                            requestCheckStatus = requestCheckResponse.json()['result']['status']
                            requestCheckProgress = requestCheckResponse.json()['result']['percentComplete']
                            requestCheckFile = requestCheckResponse.json()['result']['file']
                            print "Download is " + str(requestCheckProgress) + " complete"

                        if requestCheckStatus == 'failed' or requestCheckStatus == 'cancelled':
                            print 'FAILED OR CANCELLED, skipping'
                            continue
                        # Reset progress and filename for next survey
                        requestCheckProgress = 0
                        requestCheckFile = None
                        requestCheckStatus = 'in progress'

                        # Downloading and unzipping file
                        requestDownloadUrl = baseUrl + progressId + '/file'
                        requestDownload = requests.get(requestDownloadUrl, headers=userHeaders, stream=True)

                        f = StringIO.StringIO()
                        for chunk in requestDownload.iter_content(chunk_size=1024):
                            f.write(chunk)
                        if fileFormat == "csv":
                            zipfile.ZipFile(f).extractall('QualtricsBackup')
                        else:
                            zipfile.ZipFile(f).extractall('QualtricsBackup/XML files')

                        print 'Downloaded ' + result['name'].encode('ascii', 'replace') + '.' + fileFormat

            download_surveys(results)
            # Page through list survey results
            while resultsNextPage:
                print 'NEXT PAGE'
                nextSurveysRequestResponse = requests.get(resultsNextPage, headers=userHeaders)
                if nextSurveysRequestResponse.status_code != 200:
                    print 'NEXT PAGE retrieval failed'
                    continue
                nextResults = nextSurveysRequestResponse.json()['result']['elements']
                resultsNextPage = nextSurveysRequestResponse.json()['result']['nextPage']
                download_surveys(nextResults)
        else:
            print 'no token'

    # Store new survey status file
    with open('qualtrics-status.json', 'w') as f:
        json.dump(newSurveyStatus, f)



    print 'email sent, end of process'
    return 'all downloaded'

if __name__=='__main__':
    survey()
