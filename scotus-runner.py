# %%
# -*- coding: utf-8 -*-
import networkx as nx
from networkx.readwrite import json_graph
import argparse
import json
import pandas as pd
from lib import scrapers, grapher, citation_builders  # ,helper
import sys

argStringForInteractiveMode = [
    "--phase", "I",
    "--vStart", "584",
    "--outputFile", "cases",
    "--inputFile", "cases.json",
    "--citeOutput", "cites",
    "--graphOutput", "graph",
    "--graphFormat", "j",
    "--emailSend", "False",
]

baseURL = "https://supreme.justia.com"


def parseArgs():
    """Pulling and cleaning the CLI parameters"""
    # Add argumemts
    parser = argparse.ArgumentParser()
    # parser.add_argument(
    #    "-p", "--phase", help="Start With 1 - scrape, 2 - citation building, 3- graph building. Default 2.", type=int, default=2)
    parser.add_argument(
        "-p",
        "--phase",
        help="Individual phases of the application to run. [S]craper, [A]ppend_Scraping, [C]itation builder, [G]raph builder or [I]nteractive Mode. Full application:: first-run: 'SCG' update: 'ACG'",
        type=str,
        default="",
    )
    parser.add_argument(
        "-s",
        "--vStart",
        help="The volume to start scraping, if omitted will be minimum value",
        type=int,
        default=1,
    )
    parser.add_argument(
        "-t",
        "--vStop",
        help="The volume to stop scraping, if omitted value will be maximum available",
        type=int,
        default=None,
    )
    parser.add_argument(
        "-x",
        "--stopCase",
        help="Number of cases (int) to run through per volume. Set value=0 to run against the whole volume.",
        default=5,
    )
    parser.add_argument(
        "-o",
        "--outputFile",
        help="Output file for Case data (Scraper).",
        default="cases.json",
    )
    parser.add_argument(
        "-i",
        "--inputFile",
        help="Input file for Citation builder and Graph builder.",
        default="",
    )
    parser.add_argument(
        "-c",
        "--citeOutput",
        help="Output filename prefix (.json) for Citation builder",
        default="cites",
    )
    parser.add_argument(
        "-g",
        "--graphOutput",
        help="Output filename prefix (.gml | .json) for Graph builder",
        default="graph",
    )
    parser.add_argument(
        "-f",
        "--graphFormat",
        help="File formats for graph output: [j]son, [g]ml.  Use 'jg' for both formats",
        default="j",
    )
    parser.add_argument(
        "-e", "--emailSend", help="Send emails to mark progress", default="False"
    )
    # Set default parameters in Args; set to special values if Interactive mode or Default value (ipython issue)
    args, argsUnknown = parser.parse_known_args()
    
    #REVIEW: Convert argsForInteractiveMode dict to work properly when running in iPython
    if len(argsUnknown) > 0 or args.phase == '':
        args, argsUnknown = parser.parse_known_args(argStringForInteractiveMode)

    # Handle incorrect arg_parameters and typeCasing
    args.emailSend = False if args.emailSend != True else True
    #args.stopCase = False if args.stopCase == None else int(args.stopCase)
    args.graphFormat = args.graphFormat.strip().lower()
    return args


def main():
    """Main function to scaffold functions"""
    args = parseArgs()
    print(args)

    # Run Scraper
    if "S" in args.phase.upper() and "A" not in args.phase.upper():
        # Scrape volume main and volume detail pages to ultimately get case names and URLs
        scrape = scrapers.VolScraper(args.vStart, args.vStop, baseURL)
        volUrls = scrape.scrapeVolumes()
        caseUrls = scrape.scrapeVolumeCases(volUrls)

        # Grab cases
        cScraper = scrapers.CaseScraper(
            args.stopCase, caseUrls, args.outputFile, args.emailSend, baseURL
        )
        cases = cScraper.getCases()
        # Write cases to file
        cScraper.writeCasestoFile(cases)

    if "A" in args.phase.upper():
        # Scrape_Append case names and URLs for those not already collected
        if args.inputFile:
            # Build source dict of volume and vol_url from main source landing page
            scrapeAppend = scrapers.VolScraper(args.vStart, args.vStop, baseURL)
            volUrls_Source = scrapeAppend.scrapeVolumes()

            # Build comparison dict (vol-case counter) from existing case data (input file)
            with open(args.inputFile, "r") as fp:
                cases_Existing = json.load(fp)
                print(f"Case data loaded from {args.inputFile}")
            volCounter = scrapeAppend.getExistingVolumesCasesCount(cases_Existing)

            # Build volUrls ('update list') from the comparison of the source with our existing data
            volUrls_Append = scrapeAppend.getVolsIntersection(
                volCounter, volUrls_Source
            )
            print(f"Number of volumes reviewed: {len(volCounter)} | to update: {len(volUrls_Append)}")
            # Scrape case data from narrowed volume list
            caseUrls_Append = scrapeAppend.scrapeVolumeCases(volUrls_Append)

            # Grab cases
            cScraper_Append = scrapers.CaseScraper(
                args.stopCase, caseUrls_Append, args.outputFile, args.emailSend, baseURL
            )
            cases_Append = cScraper_Append.getCases()
            print(f"Number of cases to update: {len(cases_Append)} ")
            # Write cases to file
            if len(cases_Append) > 0:
                cScraper_Append.writeCasestoFile(
                    cScraper_Append.mergeCases(
                        cases_Existing, cScraper_Append.casesSort(cases_Append)
                    )
                )
                print(f"{args.outputFile} updated")
        else:
            print(
                f"Error.  Must specify input file arguments when using the Append_Scraping method."
            )
            exit(1)

    # Add APPEND_Method for Citation_Builder

    # Run Citation_Builder
    if "C" in args.phase.upper():
        # Load json from file if passed
        if args.inputFile and not cases:
            try:
                with open(args.inputFile, "r") as fp:
                    cases = json.load(fp)
                    print(f"Case data loaded from {args.inputFile}")
            except EnvironmentError:
                print(f"Error... {args.inputFile} is NOT a valid json input file.")

        # Run Citationbuilder if valid cases loaded
        if cases:
            CB = citation_builders.citations(cases, args.citeOutput)
            cites, metrics = CB.processText(True)
            # print cites
            print(f"   Cites: [Total, Modified, Validated, Err] -> {metrics}")
        else:
            print("No valid cases found. Please reload case information to proceed.")

    # Run Graph_Builder
    if "G" in args.phase.upper():
        if cases:
            if not (cites):
                cites = cases
            grapher.GraphBuilder(
                cites, args.graphOutput, args.graphFormat, baseURL
            ).drawGraph()
        else:
            print("No valid cases found. Please reload case information to proceed.")

    # if args.emailSend:
    #    helper.emailSend('Your Script done', "ALL DONE")

    # Run Interactive Mode
    if "I" in args.phase.upper():
        with open(args.inputFile, "r") as fp:
            cases = json.load(fp)
            print(f"Case data loaded from {args.inputFile}")

        # Need to set indexes - Number?
        df = pd.DataFrame(cases)
        df.set_index("number")


if __name__ == "__main__":
    main()

# %%
