from collections import Counter
from urllib.request import urlopen
from urllib.error import HTTPError
import re
import json
from unidecode import unidecode
import time
import datetime as dt
from lxml import html
from .helper import convertDateFromString
from .citation_builders import citations
from math import floor
import sys
#import numpy as np

# Subclass JSONEncoder to serialize dates
class DateTimeEncoder(json.JSONEncoder):
    #override the default method
    def default(self, obj):
        if isinstance(obj, (dt.date, dt.datetime)):
            return obj.isoformat()


# Class to run through the SCOTUS volumes and collect the Case Names and URLS
class VolScraper(object):
    """Class to Scrape the case names and urls from Justia's Volume Pages"""

    def __init__(self, startVol, stopVol, baseURL):
        self.startV = startVol
        self.stopV = stopVol
        self.maxV = None
        self.bURL = baseURL

    def scrapeVolumes(self):
        """Scraper Method for Volume Main Landing Page"""
        volsUrls = []
        print("VolScraper: Building Case List of URLs")

        try:
            urlLink = self.bURL+'/cases/federal/us/volume'
            volLandingHTMLreq = urlopen(urlLink).read()
        except Exception as e:
            print(f'Exception: code({e})\n Aborting request: {urlLink}')
            sys.exit(1)
        finally:
            volMainTree = html.fromstring(volLandingHTMLreq)
            volNumbersHTML = volMainTree.cssselect('div.primary-content div.wrapper span')
            #From Volume_Landing_page, get max volume number
            self.maxV = max([int(volNum.text_content()) for volNum in volNumbersHTML])
            print(f'Max volume available online is {str(self.maxV)}')

        #Check if stopV was assigned, otherwise set to maxV
        if not(self.stopV): self.stopV = self.maxV
        
        #Run scrape for Results of each Volume_page
        for i in range(self.startV, (self.stopV + 1)):
            urlLink = self.bURL+'/cases/federal/us/'+str(i)+'/'
            volsUrls.append({'vol': i, 'url':urlLink}) 
        return volsUrls


    def scrapeVolumeCases(self, volUrls):
        """Scraper Method for Volume detail pages"""
        casesUrls = []
        #Run scrape for Results of each Volume_page
        #for i in range(self.startV, (self.stopV + 1)):
        for i, volUrl in enumerate(volUrls):
            vn = volUrl['vol']
            
            #Print progress status -- volume level
            if i % 5 == 0:
                print(f'  Volume: {vn}', end=' ')
            
            #Scrape and parse volume pages
            ##UPDATE -- Should work from volsUrls list instead of re-generating links
            try:
                volHTMLreq = urlopen(volUrl['url']).read()
            except TimeoutError as e:
                print(f"Timeout Error: code({e})\n Retrying request: {volUrl['url']}")
                time.sleep(4)
                volHTMLreq = urlopen(volUrl['url']).read()
            except Exception as e:
                print(f"Exception: code({e})\n Aborting request: {volUrl['url']}")
                sys.exit(1)
            else:
                pass
            finally:
                volTree = html.fromstring(volHTMLreq)
                for searchResult in volTree.cssselect('div.search-result'):
                    resultText = unidecode(searchResult.text_content())
                    cDate = convertDateFromString(re.findall(r'[A-Z][a-z]+ \d{1,2}, \d{4}', resultText.strip()))
                    for cLink in searchResult.cssselect('a.case-name'):
                        cName = cLink.text_content().split(':')[0].strip()
                        if cName != "https": casesUrls.append({'url': cLink.get('href'), 'vol': vn, 'caseName': cName, 'date': cDate[0] if cDate else None})
        
            #Print progress status -- case level
            if i % 5 == 0:
                casesCount = len([case['vol'] for case in casesUrls if case['vol'] > int(vn)-5])
                print(f'| Cases: {casesCount}')        
        print("VolScraper: Done")
        return casesUrls


    def getExistingVolumesCasesCount(self, cases):
        """Get case counts by volume from a Cases_dict. Checks only between start and stop volumes initially entered"""        
        return Counter([case['vol'] for case in cases 
                        if case['vol'] >= self.startV and case['vol'] <= self.stopV and case['vol'] < self.maxV])
        

    def getVolsIntersection(self, volCasesCounter_fromFile, volUrls_Source):
        """Creates a list of volumes (dict(vol, url)) present in Source dict (counter) that are not present in existing data from file"""
        return [{'vol': vol['vol'], 'url': vol['url']} for vol in volUrls_Source 
                if vol['vol'] not in volCasesCounter_fromFile.keys()]
        


###Case Build Scraper Class###
class CaseScraper(object):
    """Class to scrape individual case urls and case subpages from a corpus of caseurls
    Args:
        Expects the output from the VolScraper.scrapeVolumes 
    """

    def __init__(self, stopCase, caseLinks, outfile, emails, baseurl):
        self.stopCase = stopCase
        self.caseLinks = caseLinks
        self.outfile = outfile + '.json'
        self.emails = emails
        self.baseURL = baseurl


    def parseDockFromUrl(self, url):
        """Extracts the case docket page number from the case's url.

        Notes:
         Has special handling for cases of original jurisdiction.
         This is apparently the best way to grab the docket number without regex.
        """
        dock = url.split('/')[-2].split('-')[-1]

        if re.match('\d*orig', dock) or re.match('^[0-9]+[a-zA-Z]{1,2}[0-9]*$', dock):      #added case to handle non-alpha docket numbers
            dock = dock
        else:
            dock = int(dock)
        return dock
 

    def deleteDisclaimer(self, text):
        """Removes Justia disclaimers from the casetext"""
        #Add new disclaimers as element to 'disclaimers' list
        disclaimers = ['Disclaimer: Official Supreme Court case law is only found in the print version of the United States Reports. Justia case law is provided for general informational purposes only, and may not reflect current legal developments, verdicts or settlements. We make no warranties or guarantees about the accuracy, completeness, or adequacy of the information contained on this site or information linked to from this site. Please check official sources.'
                       ,'Justia Annotations is a forum for attorneys to summarize, comment on, and analyze case law published on our site. Justia makes no guarantees or warranties that the annotations are accurate or reflect the current state of law, and no annotation is intended to be, nor should it be construed as, legal advice. Contacting Justia or any attorney through this site, via web form, email, or otherwise, does not create an attorney-client relationship.'
                      ]
        for disclaimer in disclaimers:
            text = text.replace(disclaimer, "")
        return text


    def caseParse(self, caseHtml):
        """Extract the opinion text from the html return"""
        caseTree = html.fromstring(caseHtml)
        opinionTypesHTML = caseTree.cssselect('div#tab-opinion ul.tab-nav li.nav-item')
        opinionsHTML = caseTree.cssselect('div#tab-opinion > div')
        opinionSummaryHTML = caseTree.cssselect('div.primary-content div.block, div.primary-content div.large') 
        mediaLinksHTML = caseTree.cssselect('div#tab-audio-and-media tbody > tr td a')

        #sidebarHTML = caseTree.cssselect('div#primary-sidebar')
        downloadPDFHTML = caseTree.cssselect('div#primary-sidebar aside.widget.annotation.jcard p a')

        opinionTypes = [unidecode(ot.text_content().strip()) 
            for ot in opinionTypesHTML]

        opinions = [self.deleteDisclaimer(unidecode(o.text_content().strip())) 
            for o in opinionsHTML]

        cites = [citations.extractCitations(o) 
            for o in opinions]

        opinionSummary = [self.deleteDisclaimer(unidecode(opSummary.text_content().strip())) for opSummary in opinionSummaryHTML]

        mediaLinksTxt = [unidecode(mLText.text_content()) for mLText in mediaLinksHTML]
        mediaLinksURL = [unidecode(mLURL.attrib['href']) for mLURL in mediaLinksHTML]
        media = [{'txt':mt, 'url':mL} for mt, mL in zip(mediaLinksTxt, mediaLinksURL)]
        
        pdfCaseURL = (unidecode(downloadPDFHTML[0].attrib['href']) if downloadPDFHTML else None)
        updDate = dt.date.today()

        return opinionSummary, opinionTypes, opinions, cites, media, pdfCaseURL, updDate


    def fetchCase(self, caseUrl):
        """Make the request to Justia to grab the page for the case"""

        url = self.baseURL + caseUrl
        try:
            htmlResp = urlopen(url).read()
        except HTTPError as e:
            return None, None
        else:
            opinionSummary, textTypes, texts, cites, media, pdfCaseURL, updDate = self.caseParse(htmlResp)
            return opinionSummary, textTypes, texts, cites, media, pdfCaseURL, updDate



    def getCases(self):
        """The scaffold method for the whole class."""
        lt = time.asctime(time.localtime(time.time()))
        problemCases, cases = [], []
        cL = self.caseLinks
        if self.stopCase == None or (self.stopCase != None and len(cL) < self.stopCase):
            end = len(cL)
            print("Total Number of Cases: " + str(end))
        else:
            end = self.stopCase
    
        print('CaseScraper: Started')

        # for sometimes count variables to only print once -- for email processing
        lastVol, lastPer = 0, -1
        
        # Loop through cases
        for c in range(end):
            vol = cL[c]['vol']
            dock = self.parseDockFromUrl(cL[c]['url'])
            cNum = [vol, dock]
            if vol % 5 == 0 and vol > lastVol:
                print(f'   Volume: {vol}')
                lastVol = vol

            opinionSummary, textTypes, texts, cites, media, pdfCaseURL, updDate = self.fetchCase(cL[c]['url'])

            # Add to the list of cases the case information
            cases.append({'name': cL[c]['caseName'], 'url': cL[c]['url'], 'txt_type': textTypes, 'txt': texts, 'opinion_summary': opinionSummary,
                         'number': cNum, 'citations': cites, 'vol': cL[c]['vol'], 'date': cL[c]['date'], 'media': media, 'pdfURL': pdfCaseURL, 'updDate': updDate})
            
            # Save every hundred cases
            #if c % 100 == 0:
            #    with open(self.outfile, 'w') as fp:
            #        json.dump(cases, fp, indent=2)
            #
            # Email every 10% of cases
            #per = int(floor((float(c)/float(end)*100)))
            #if per % 10 == 0 and self.emails and per > lastPer:
            #    helper.sendEmail(per, c, end, lt)
            #    lastPer = per
            # Save at the end of the loop
        
        print(f'   Problem cases while scraping: {problemCases}')
        print('CaseScraper: Done')
        return cases


    def writeCasestoFile(self, cases):
        """Saves case_dict to json file format as specified initially"""
        print('Saving case data to file.')
        with open(self.outfile, 'w') as fp:
            json.dump(cases, fp, indent=2, cls=DateTimeEncoder)
        print(f'Case data saved as {self.outfile}')


    def mergeCases(self,cases_X, cases_Y):
        """Merges and dedupes two case_dicts"""
        cases_XY = []
        for case_X in cases_X:
            if case_X not in cases_XY: cases_XY.append(case_X) 
        for case_Y in cases_Y:
            if case_Y not in cases_XY: cases_XY.append(case_Y) 
        return cases_XY

    def casesSort(self,cases):
        """Sorts cases dict on number (tuple: vol, case) and returns a new cases dict"""
        sortedCases = cases
        sortedCases.sort(key= lambda item: (item.get('number')[0], item.get('date') if item.get('date') else 'ZZZZ', item.get('number')[1] if type(item.get('number')[1]) is int else 9999))

        return sortedCases