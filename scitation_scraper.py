from __future__ import print_function

import argparse
import json
import re
import requests
import time
import webbrowser
import xml.etree.ElementTree as et


class ScitationScraper:
    def __init__(self, tex_file, debug=False):
        self.names = []
        self.check_manually = []
        
        self.get_bibtex_items(tex_file)
        
        self.get_doi()
        self.parse_no_doi_refs()
        self.get_names_arxiv_refs()
        self.get_names_doi_refs()
        self.get_unique_names()
        if not debug:
            self.open_google_pages()
        self.parse_manually_checked_references()

    def parse_manually_checked_references(self):
        if len(self.check_manually) == 0:
            print("There are no reference to check manually.")
        else:
            # TODO: Handle doi's that have to be handchecked nicely (open them automatically).
            print("The following references have to be checked by hand:")
            for ref in self.check_manually:
                print(ref, '\n')

            
    def get_bibtex_items(self, tex_file):
        with open(tex_file, 'r') as f:
            tex_source = f.read()
        bibitem_regex = re.compile(r"\\bibitem{.*?}(.+?)(?=\\bibitem{|\\end{thebibliography})", re.DOTALL)
        self.references = bibitem_regex.findall(tex_source)
        
    def get_doi(self):
        self.all_dois = []
        self.no_dois = []
        for ref in self.references:
            try:
                doi = re.search(r"\\doi{(.*?)}", ref).group(1)
                self.all_dois.append(doi.rstrip('/'))
            except AttributeError:
                self.no_dois.append(ref)

    def parse_no_doi_refs(self):
        """Parse references without doi's."""
        self.arxiv_ids = []
        for ref in self.no_dois:
            if "arxiv" in ref:
                arxiv_id = re.search(r"\\href{.*?}{arXiv:(.*?)}", ref).group(1)
                self.arxiv_ids.append(arxiv_id)
            else:
                if re.search(r"\(20\d{2}\)", ref):
                    self.check_manually.append(ref)

    def get_names_doi_refs(self):
        """ Extract author names associated with DOI's. """
        for i, ref in enumerate(self.all_dois):
            try:
                api_data = json.loads(requests.get("https://api.crossref.org/works/{}".format(ref), timeout=10).text)
            except requests.exceptions.Timeout:
                self.check_manually.append(ref)
                print("failed (connection timeout)")
                continue
            year = api_data['message']['issued']['date-parts'][0][0]
            print("Processing doi {0:>3} of {1}... ".format(i + 1, len(self.all_dois)), end='')
            if year is None:
                self.check_manually.append(ref)
                print("failed (no year specified in api response)")
                continue
            try:
                if year >= 2000:
                    authors = api_data['message']['author']
                    for a in authors:
                        self.names.append("{0} {1}".format(a['given'], a['family']))
                    print("succes (result from 2000 or later)")
                else:
                    print("succes (result too old)")
            except KeyError:
                self.check_manually.append(ref)
                print("failed (no authors specified in api response)")

    def get_names_arxiv_refs(self):
        # TODO: Get author names from XML api replies.
        for i, ref in enumerate(self.arxiv_ids):
            try:
                data = requests.get("https://export.arxiv.org/api/query?search_query={}".format(ref), timeout=10).text
            except requests.exceptions.Timeout:
                self.check_manually.append(ref)
                continue
            root = et.fromstring(data)
            print("root", root)
        
    def get_unique_names(self):
        """ Get unique names from a list of names. """
        name_dict = {}
        for name in list(set(self.names)):
            full_name = re.sub("\s\s+" , " ", name.replace('.', ' '))  # Remove any dots and extraneous whitspace.
            abbrv_name = full_name
            # Create a normalized name that can be used to compare names with different levels of abbrevation.
            # TODO: Remove any accents and special characters from names to improve comparison.
            abbrv_name = ' '.join([n[:1] for n in abbrv_name.split(' ')[:-1]] +  [abbrv_name.split(' ')[-1]])
            abbrv_name = abbrv_name.lower()
            if abbrv_name not in name_dict or len(name_dict[abbrv_name]) < len(full_name):
                name_dict[abbrv_name] = full_name
        self.unique_names = list(name_dict.values())
        #print(self.unique_names)

    def open_google_pages(self):
        print("Opening Google search pages (in batches of 10)")
        for index, name in enumerate(sorted(list(self.names))):
            webbrowser.open("https://www.google.com/search?q={0}+physics".format(name.replace(' ', '+')))
            if (index + 1) % 10 == 0:
                input("Press enter to open next 10...")

    @staticmethod
    def cli_parsing():
        parser = argparse.ArgumentParser()
        parser.add_argument('tex_file')
        args = parser.parse_args()
        return args

if __name__ == '__main__':
    args = ScitationScraper.cli_parsing()
    scitation_scraper = ScitationScraper(args.tex_file, debug=False)
