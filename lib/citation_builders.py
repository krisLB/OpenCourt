import regex
import json
import unidecode
import time
from itertools import chain


class citations(object):
    """A separate class to just build and validate the case citations"""

    def __init__(self, cases, outfile):
        self.cases = cases
        self.outfile = outfile+".json"

    #ADD NEW METHOD?
    #def isValidVol(self):
        #Valid definition for: vol >= min(1) and <= max(parse?) && must exists in CASES (can't run Citations if no underlying Case data)
        #Valid definition for: dock >= min(parse?) and <= max (parse?) && must exist in CASES
    #    pass

    @staticmethod
    def extractCitations(case):
        """ Uses Regular expressions to extract the estimated citations from the case text
        Previously from the scrapers class as caseExtract
        Args:
                The text of a case
        Returns:
                A list of citations

        """
        #Citation Format Example: 123 U.S. 2345
        #citeList = regex.findall('(?<!Page|P.) ?\d{1,3} U\. ?S\. \d{1,4} \(\S*\)', case)
        citeList = regex.findall('(?<!Page|P.) ?\d{1,3} U\. ?S\. \d{1,4}', case)   #Update?
        v = []

        # Get Volume
        for i,citeItem in enumerate(citeList):
            d = regex.findall('^\d{1,3}', citeItem.strip())
            s = regex.findall('(?<= )\d{1,4}$', citeItem.strip())
            #CHECK IF VALID BEFORE ADDING -- INVALID NEEDS TO GO TO PROBLEM LIST
            v.append([int(d[0]), int(s[0])])
        return v

    def cascadeCase(self, citation, caseDict, volumes):
        """ Find the case from the page of the citation (first page of the case)
        Previously "checkCase" in the Grapher Class
        """
        if citation in caseDict:
            return 1, citation
        else:
            # where volume == citation[0], case where floor of case
            # limit search to this volume
            v = citation[0] - 1
            # assign to the lower case
            if v < len(volumes):
                for c in volumes[v]:
                    if citation[1] > c:                 #_EVAL_: LowCite doesn't work. Not sure what it accomplishes               
                        lowCite = [citation[0], c]
                        return 0, lowCite
            else:
                return 0, citation
        return 0, None

    def citeToName(self, cite):
        """Checks if a citation links to a casename"""
        for c in self.cases:
            # print(nameList[c]['number'])
            if cite == c['number']:
                return c['name']
        return None

    def validateName(self, name, caseToCheck):
        if caseToCheck.lower().find(name.lower()) != -1:
            return True
        else:
            return False

    def buildVolCaseList(self):
        """Assign each case to a nested Volume List for faster hashing"""
        vols, cL = [], []
        for i in range(597):   #_EVAL_ : update to dynamic range
            vols.append([])
        for c in self.cases:
            v = c['number'][0] - 1  #volume
            vols[v].append(c['number'][1])
            cL.append(c['number'])
        for i in range(597):   #_EVAL_ : update to dynamic range
            #vols[i].sort()
            vols[i].sort(key=lambda o: list(map(int,regex.findall(r'\b\d{1,4}',str(o))))) #need complex sort to handle alpha-numeric
        return vols, cL

    def matchMetrics(self, totalCitations, modified, validated, errs):
        """Evaluate the performance of the matching algorthims"""
        tc = float(totalCitations) + 0.001
        return [tc, float(modified)/tc, float(validated)/tc, float(errs)/tc]

    def processText(self, save_text):
        """Scaffold for the class"""
        print('CitationBuilder: Started')
        vols, caseList = self.buildVolCaseList()
        case_citations = []

        for ic,case in enumerate(self.cases):
            if (ic % 100 == 0):
                print(f'   Case block: {ic}/{len(self.cases)}')

            cites = [self.extractCitations(cTxt) for cTxt in case['txt']]
            citesAll = [cl for citeList in cites
                        for cl in citeList]
            cleaned = []

            # Metrics for how many citations were modified tc= Total Citations/ MC modified/ vC Validated
            totalCount, modifiedCount, validatedCount, errorCount = 0, 0, 0, 0
            for c, cite in enumerate(citesAll):
                totalCount += 1
                x, chckd = self.cascadeCase(cite, caseList, vols)
                modifiedCount += x
                
                if not chckd:
                    #Error where None (No Citation) passed back from cascadeCase
                    errorCount += 1
                elif (chckd != case['number']):
                    n = self.citeToName(chckd)
                    if n:
                        caseTxtAll = ' '.join([str(txt) 
                                            for txt in case['txt']])
                        validatedCount += 1 if self.validateName(n, caseTxtAll) else 0
                        if chckd not in cleaned: cleaned.append(chckd)
                    else:
                        errorCount += 1
            # if len(cleaned) > 0:
            # 	print cleaned
            if save_text:
                case_citations.append({'name': case['name'], 'url': case['url'], 'txt': case['txt'],
                                      'number': case['number'], 'citations': cleaned, 'vol': case['vol'], 'date': case['date']})
            else:
                case_citations.append({'name': case['name'], 'url': case['url'], 'number': case['number'],
                                      'citations': cleaned, 'vol': case['vol'], 'date': case['date']})
        with open(self.outfile, 'w') as fp:
            json.dump(case_citations, fp, indent=2)
        metrics = self.matchMetrics(totalCount, modifiedCount, validatedCount, errorCount)
        print('CitationsBuilder: Done')
        return case_citations, metrics
