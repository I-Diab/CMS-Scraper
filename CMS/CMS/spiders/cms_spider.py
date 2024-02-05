from typing import Any, Generator
import scrapy
from scrapy import Selector
from scrapy.http import Request, Response
from dotenv import load_dotenv
import os
import re

load_dotenv()

class CMSSpider(scrapy.Spider):
    name = "cms"

    http_user = None 
    http_pass = None 
    output_path = None

    base_url = "https://cms.guc.edu.eg"
    start_urls = [
        f"{base_url}/apps/student/HomePageStn.aspx"
    ]

    def __init__(self, **kwargs: Any) -> None:
        """
            Defined to allow credentials and output path through env variables if not given as arguments
        """
        super().__init__(**kwargs)

        self.http_user = "GUC\\"+(self.http_user or os.getenv('HTTP_USER'))
        self.http_pass = self.http_pass or os.getenv('HTTP_PASS')
        self.output_path = self.output_path or os.getenv('OUTPUT_PATH')
        print(self.http_user, self.http_pass, self.output_path)

    def parse(self, response: Response) -> Generator[Request,None,None]:
        """ This method is responsible for parsing the home page to get the course name and id that the url depends on

        Args:
            response (Response): The response got from the start_url

        Yields:
            Generator[Request]: The requests needed to fetch the courses' pages
        """
        print("Parsing Home Page ...")
        subjects = response.css("table#ContentPlaceHolderright_ContentPlaceHoldercontent_GridViewcourses tr")
        subjects.pop(0) # Removing the header of the table

        for subject in subjects:
            course_name = subject.css("td::text").getall()[2]
            course_id = self.extract_course_id(course_name)
            course_url = self.get_course_url(course_id)
            self.create_course_dir(course_name)
            yield response.follow(course_url, callback=self.parse_course_page, cb_kwargs={"course_name": course_name})
       

    def parse_course_page(self, response: Response, course_name: str) -> Generator[Request,None,None]:
        """ Parses course_name's page by extracting urls of each file to be downloaded in addition to any other needed info

        Args:
            response (Response): The response got from the request made to fetch the course's page
            course_name (str): The name of the course that the page is associated with

        Yields:
            Generator[Request]: The requests that will be made to download the files
        """

        print(f"Parsing {course_name} Page ...")
        cards = response.css("div.card-body")
        
        for card in cards:
            content_type = self.get_content_type(card)
            content_name = self.get_content_name(card)
            content_url = self.get_content_url(card)

            file_dir = self.create_type_dir(course_name, content_type)

            cb_kwargs = {
                'file_dir': file_dir,
                'content_name': content_name
            }

            yield Request(content_url, self.handle_downloaded_file, cb_kwargs=cb_kwargs)


    def handle_downloaded_file(self, response: Response, file_dir: str, content_name: str) -> None:
        """This method is responsible for saving the file after getting its path

        Args:
            response (Response): The response got from the request made to fetch the file
            file_dir (str): The directory which the file should be saved in
            content_name (str): The name that the file should be named with
        """
        
        extension = response.url.split(".")[-1] # get the extenstion from the url to be added to the path
        path = "/".join([file_dir, content_name])
        path = ".".join([path,extension])

        if(not os.path.isfile(path)):
            with open(path, "wb") as f:
                f.write(response.body)
            print(f"Downloaded and saved {content_name} in {file_dir}")



    #### Hepler methods

    def extract_course_id(self, course_name: str) -> str:
        return course_name.split(" ")[-1][1:-1]

    def get_course_url(self, course_id: str, sid:str = "62") -> str:
        return f"https://cms.guc.edu.eg/apps/student/CourseViewStn.aspx?id={course_id}&sid={sid}"
    
    def get_content_type(self, card: Selector) -> str:
        content_type = card.css("div div::text").getall()[0]
        return re.search(r'\((.*?)\)',content_type).group(1).strip() # Extract content_type by removing brackets and spaces if any

    def get_content_name(self, card: Selector) -> str:
        return card.css("div strong::text").get()[4:] # Remove the numbering of each week (e.g. removing "1 - " in "1 - Lecture 10")
    
    def get_content_url(self, card: Selector) -> str:
        return self.base_url+card.css("div a#download::attr(href)").get()
    
    def create_course_dir(self, folder_name: str) -> str:
        path = self.output_path+"/"+folder_name
        path = path.replace("|","")
        if(not os.path.exists(path)):
            os.mkdir(path)
            print(f"Created {folder_name}")
        
        return path

    def create_type_dir(self, course_name: str, folder_name: str) -> str:
        path = "/".join([self.output_path, course_name, folder_name])
        path = path.replace("|","")
        if(not os.path.exists(path)):
            os.mkdir(path)
            print(f"Created {folder_name} in {course_name}")
        
        return path