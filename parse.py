# -*- coding: utf-8 -*-
# Some functions that will help with parsing lexisnexis results

import sys
import getopt
import re
import glob
import argparse
import csv
import os.path
from collections import defaultdict
import logging
from urllib.parse import urlparse

document_boundary = "\d+ of \d+ DOCUMENTS?.{0,1}"

def getcolumns(fullstr,percent=10):
    """
    Return the names of the columns for which we have metadata.

    Keyword arguments:
    fullstr -- The full text of the lexisnexis file, in a string.
    percent -- The minimum percentage of occurences needed to include a column.
               (default: 10)
    """
    allsplits = re.split(document_boundary,fullstr)
    all_cols = defaultdict(lambda: dict({'document_total':0,'total_occurances':0}))
    for i,s in enumerate(allsplits[1:]):
        cols = re.findall("\n([A-Z\-]+): .+",s)
        d = dict()
        for c in cols:
            if c in d:
                d[c] += 1
            else:
                d[c] = 1
        for c in d:
            all_cols[c]['document_total'] += 1
            all_cols[c]['total_occurances'] += d[c]
            all_cols[c]['term_average'] = float(all_cols[c]['document_total']/all_cols[c]['total_occurances'])
    return [c for c in list(all_cols.keys()) if all_cols[c]['term_average'] ==1 and (all_cols[c]['total_occurances']/len(allsplits))*100 > float(percent)]

def splitdocs(fullstr,topmarker=["TEXT", "LENGTH","DATELINE", "[0-9]+\sword"],bottommarker=["LOAD-DATE"],colnames=["LENGTH"],dodate=False,docopyright=False):
    """
    Return a list of dictionaries containing articles and metadata.

    In general, this script will attempt to pull the text between the topmarker and bottommarker.
    If the topmarker and bottommarker are not found, the text will not be included.
    Keyword arguments:
    fullstr -- The full text of the lexisnexis results, in a string
    topmarker -- The last piece of metadata before an article (default: "LENGTH")
    bottommarker -- The first piece of metadata after an article (default: "LOAD-DATE")
    colnames -- The list of metadata names in a list (default: ["LENGTH"])
    """
    if colnames is None or len(colnames)==0:
        colnames = ["LENGTH"]
    # process the column names for the copyright line
    if colnames is not None and len(colnames)>0:
        oldcolnames = colnames
        colnames = []
        for c in oldcolnames:
            if c.upper() != 'COPYRIGHT':
                colnames.append(c)
            else:
                # copyright is handled differently, but people can enter it the same way
                docopyright = True

    allsplits = re.split(document_boundary,fullstr)
    articles = []
    for i,s in enumerate(allsplits[1:]):
        #import code; code.interact(local=locals())
        topmarkerstr = str("|".join(str(x) for x in topmarker))
        header = s
        if topmarker is not None and re.search("\n("+ topmarkerstr +").+?\n",s) is not None:
            headermarker = re.findall("\n("+topmarkerstr+").+?\n",s)[-1]
            headersplit = re.split("\n"+headermarker+".+?\n",s)
        else:
            headersplit = re.split(r'(?:.{0,10}? \d{1,2}, \d{4}(?: .[A-z]+?day)?)(?: \d{1,2}:\d{2} ?AM|PM)?(?: [A-Z]{1,3})?', s, 1)

        if len(headersplit) > 1:
            header = headersplit[0]
            header_props = re.split('\n\s*\n', header.strip())
            body = headersplit[1]
        else:
            header = ''
            body = s
            header_props = []
            if topmarker is not None:
                logging.info("*** Marker %s not found in article %s ***" % (topmarkerstr, i + 1))

        bottommarkerstr = str("|".join(bottommarker))
        if bottommarker is not None and re.search("\n("+bottommarkerstr+").+?\n",body) is not None:
            footermarker = re.findall("\n("+bottommarkerstr+").+?\n",s)[-1]
            bottomsplit = re.split("\n"+footermarker+".+?\n",body)
            body = bottomsplit[0]
            footer = bottomsplit[1]
        else:
            footer = ''
            body = body
            if bottommarker is not None:
                logging.debug("*** Marker %s not found in article %s ***" % (bottommarkerstr, i+1))

        d = dict.fromkeys(colnames)
        d['header'] = header
        num_headers = len(header_props)
        if header_props is not None and num_headers > 0:
            if num_headers > 1:
                d['sug_publication'] = header_props[0]
                if num_headers > 2:
                    if header_props[2].startswith('http') and header_props[0] == 'View Full Results Online':
                        d['sug_pub_date'] = header_props[3]
                        d['sug_title'] = header_props[4]
                    else:
                        d['sug_pub_date'] = header_props[1]
                        d['sug_title'] = header_props[2]
                else: d['sug_title'] = header_props
            else: d['sug_title'] = header_props[0]
        if dodate:
            d['Date'] = None
        d['text'] = body.strip()
        for c in colnames:
            res = re.findall("\n"+c+":(.+)?(\r|\n)",s)
            if len(res)>0:
                d[c] = res[0][0].strip()
        if docopyright:
            try:
                copyresult = re.findall(r'\n\s+(Copyright|\N{COPYRIGHT SIGN}|©)\s+(.*)\n',s,flags=re.IGNORECASE)
                d['COPYRIGHT'] = copyresult[0][1].strip()
            except:
                print("*** Copyright line not found in article", i+1)
        if dodate:
            try:
                dateresult = re.findall(r'\n\s{5}.*\d+.*\d{4}\s',s,flags=re.IGNORECASE)
                if header:
                    dateresult += re.findall(r'\w+\s\d+.*\d{4}', header)
                    dateresult += re.findall(r'\w+\s*\d{4}', header)
                d['Date'] = dateresult[0].strip()
            except:
                print("*** Date line not found in article", i+1)

        articles.append(d)
    return articles

def islink(link):
    parseResult = urlparse(link)
    if parseResult.scheme in ['http','https']:
        #its a valid url
        print(link)





def main():
    parser = argparse.ArgumentParser(description='Parse output from Lexis Nexis.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-d','--directory', help='the path containing multiple lexis nexis files (e.g. /users/me/data)', required=False, nargs=1)
    group.add_argument('-f','--file', help='individual file(s) to process (e.g. /Users/jdoe/Downloads/foo.txt)', required=False, nargs='*')
    parser.add_argument('-c','--csvfile', help='the csv file containing the metadata', required=False, nargs=1)
    parser.add_argument('-o','--outfiles', help='the directory to write individual articles to', required=False, nargs=1)
    parser.add_argument('-dmy','--date', help='look for a line with a date', required=False, action="store_true")
    parser.add_argument('-m','--metadata', help='the metadata to scrape from individual articles', required=False, nargs='*')
    parser.add_argument('-b','--boundaries', help='the metadata before an article begins, and after it ends.  If there is only a beginning or ending metadata tag, use None.', required=False, nargs=2)

    args = vars(parser.parse_args())

    if args['directory'] is not None:
        files = glob.glob(args['directory'][0]+os.path.sep+'*.txt') + glob.glob(args['directory'][0]+os.path.sep+'*.TXT')
    elif args['file'] is not None:
        files = args['file']

    fieldnames = []
    if args['outfiles'] is not None:
        fieldnames += ['filename','originalfile']
    if args['metadata'] is not None:
        fieldnames += args['metadata']
    if args['date']:
        fieldnames += ['Date']
        print(fieldnames)
    if args["csvfile"] is not None:
        fcsv = open(args["csvfile"][0],'w')
        dw = csv.DictWriter(fcsv, delimiter='\t', fieldnames=fieldnames)
        dw.writeheader()
    else:
        fcsv = False

    if args["boundaries"] is not None:
        bstart = args["boundaries"][0]
        if bstart == 'None':
            bstart = None
        bend = args["boundaries"][1]
        if bend == 'None':
            bend = None

    if args["boundaries"] is not None:
        bstart = args["boundaries"][0]
        if bstart == 'None':
            bstart = None
        bend = args["boundaries"][1]
        if bend == 'None':
            bend = None

    outputs = []

    counter = 0
    for f in files:
        fp = open(f,'r', encoding='latin-1')
        print("Processing file: ", f)
        #splitdocs(fullstr,topmarker="LENGTH",bottommarker="LOAD-DATE",colnames=["LENGTH"]):
        if args['boundaries'] is not None:
            outputs = splitdocs(fp.read(),topmarker=bstart,bottommarker=bend,colnames=args['metadata'],dodate=args['date'])
        else:
            print(fp.read())
            outputs = splitdocs(fp.read(),colnames=args['metadata'],dodate=args['date'])
        print("...............{} articles found".format(len(outputs)))
        if args["outfiles"] is not None:
            for art in outputs:
                #import code; code.interact(local=locals())
                fname = "{direc}{sep}{c:08d}.txt".format(direc=args['outfiles'][0],sep=os.path.sep,c=counter)
                fw = open(fname,'w')
                fw.write(art['text'])
                counter+=1
                fw.close()
                if fcsv:
                    art.pop('text')
                    art['filename'] = fname
                    art['originalfile'] = f
                    dw.writerow(art)
        elif fcsv:
            for art in outputs:
                art.pop('text')
                dw.writerow(art)

    if fcsv:
        fcsv.close()

if __name__ == '__main__':
    main()