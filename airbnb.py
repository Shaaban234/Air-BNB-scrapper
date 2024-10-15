import json
import asyncio
import aiohttp
from requests_html import AsyncHTMLSession
from bs4 import BeautifulSoup
import pandas as pd
import requests
from datetime import datetime
import re
import warnings
import asyncpg
import random
from requests_html import AsyncHTMLSession

with open("user-agents.txt", "r") as file:
    user_agents = file.readlines()
user_agents = [agent.strip() for agent in user_agents if agent.strip()] 
warnings.filterwarnings("ignore", category=DeprecationWarning)

df = pd.DataFrame()  # Create an empty DataFrame
listing_data = []  # List to store dictionaries of each listing's data
async def fetch_url(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def url():
    try:
        # Get user input for destination
        destination = input("Enter destination place: ")
        

        # Get user input for start date
        while True:
            start_date_str = input("Enter start date (YYYY-MM-DD): ")
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                break
            except ValueError:
                print("Invalid date format. Please enter the date in the format YYYY-MM-DD.")

        # Get user input for end date
        while True:
            end_date_str = input("Enter end date (YYYY-MM-DD): ")
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
                if end_date < start_date:
                    print("End date cannot be before start date. Please enter a valid end date.")
                else:
                    break
            except ValueError:
                print("Invalid date format. Please enter the date in the format YYYY-MM-DD.")

        # Format the dates
        start_date_formatted = start_date.strftime("%Y-%m-%d")
        end_date_formatted = end_date.strftime("%Y-%m-%d")

        urls = set()  # Use a set to store unique URLs

        # Pagination loop
        page_num = 1
        while page_num <= 1:
            # Construct the modified link with pagination
            modified_link = f"https://www.airbnb.com/s/{destination}/homes?tab_id=home_tab&refinement_paths%5B%5D=%2Fhomes&flexible_trip_lengths%5B%5D=one_week&monthly_start_date={start_date_formatted}&monthly_length=3&monthly_end_date={end_date_formatted}&price_filter_input_type=0&source=structured_search_input_header&search_type=autocomplete_click&page={page_num}"
            print(modified_link)
            html_content = await fetch_url(modified_link)

            # Parse the HTML content with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Find elements containing the URL pattern
            url_elements = soup.find_all('a', href=True)
                
            for element in url_elements:
                # Try to extract the URL from the href attribute
                url = element.get('href')
                if url and url.startswith('/rooms/'):
                    urls.add("https://www.airbnb.com" + url)  

            # Find button for next page
            next_page_button = soup.find('button', {'aria-label': 'Next'})
            if not next_page_button:
                break

            # Increment page number for next iteration
            page_num += 1
        i=1
        if urls:
            for url in urls:
                #calls
                await  get_airbnb_data(url)
                print("Index :",i,"URL:", url)
                i+=1
        else:
            print("No URLs found.")

    except Exception as e:
        print("An error occurred:", e)
    

def get_airbnb_price(url):
    headers = {'User-Agent': random.choice(user_agents)}  
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find elements containing the price
    price_elements = soup.find_all(text=re.compile(r'\$\d+'))

    price = None
    for element in price_elements:
        # Try to extract the price from the text
        match = re.search(r'\$\d+', element)
        if match:
            price = match.group(0)
            break  # Exit loop if price is found

    if price:
        return price
    else:
        return "Price not found."

def extract_html_text(data):
    # Check if the input data is a dictionary
    if isinstance(data, dict):
        # Iterate over the key-value pairs
        for key, value in data.items():
            # Check if the key is 'htmlText'
            if key == 'htmlText':
                # Return the value if found
                return value
            else:
                # If the value is another dictionary or list, recursively call the function
                result = extract_html_text(value)
                # If the result is not None, return it
                if result is not None:
                    return result
    # If the input data is a list, iterate over each item
    elif isinstance(data, list):
        for item in data:
            # Recursively call the function for each item
            result = extract_html_text(item)
            if result is not None:
                return result
    # If no 'htmlText' is found, return None
    return None

def extract_Description(abd, typename, field):
    results = []

    # Traverse the JSON to find the specified 'typename' and extract 'field'
    def traverse(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == '__typename' and value == typename:
                    results.append(obj.get(field))
                else:
                    traverse(value)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    # Call the traverse function
    traverse(abd)

    return results

def extract_bed_info(abd, typename, field):
    results = []

    # Traverse the JSON to find the specified 'typename' and extract 'field'
    def traverse(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == '__typename' and value == typename:
                    results.append(obj.get(field))
                else:
                    traverse(value)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    # Call the traverse function
    traverse(abd)

    return results

def extract_title_from_json(data):
    titles = []

    def traverse(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == '__typename' and value == 'PdpSharingConfig':
                    titles.append(obj.get('title'))
                else:
                    traverse(value)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    # Call the traverse function
    traverse(data)

    return titles

def extract_ratings(data, ratings_dict):
    # Check if the data is a dictionary
    if isinstance(data, dict):
        for key, value in data.items():
            # Check if the key is one of the specified ratings
            if key in ["accuracyRating", "checkinRating", "cleanlinessRating",
                       "communicationRating", "locationRating", "valueRating",
                       "guestSatisfactionOverall"]:
                # Add the rating name and value to the dictionary
                ratings_dict[key] = value
            else:
                # If the value is a dictionary or list, recursively call the function
                extract_ratings(value, ratings_dict)
    
    # Check if the data is a list
    elif isinstance(data, list):
        for item in data:
            # Recursively call the function for each item in the list
            extract_ratings(item, ratings_dict)

def extract_amenities(data, amenity_names):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'amenities' and isinstance(value, list):
                for amenity in value:
                    if isinstance(amenity, dict):
                        amenity_names.append(amenity.get('title'))
            else:
                extract_amenities(value, amenity_names)
    elif isinstance(data, list):
        for item in data:
            extract_amenities(item, amenity_names)

def extract_host_titles(data, typename, titles):
    if isinstance(data, dict):
        if "__typename" in data and data["__typename"] == typename:
            titles.append(data["title"])
        else:
            for value in data.values():
                extract_host_titles(value, typename, titles)
    elif isinstance(data, list):
        for item in data:
            extract_host_titles(item, typename, titles)

def extract_listing_title(data, listing_titles):
    if isinstance(data, dict):
        if "__typename" in data and data["__typename"] == "AvailabilityCalendarSection":
            listing_titles.append(data["listingTitle"])
        else:
            for value in data.values():
                extract_listing_title(value, listing_titles)
    elif isinstance(data, list):
        for item in data:
            extract_listing_title(item, listing_titles)

def extract_reviews_data(data, typename, reviews):
    if isinstance(data, dict):
        if "__typename" in data and data["__typename"] == typename:
            review_data = {
                "averageRating": data["averageRating"],
                "reviewsCountAccessibilityLabel": data["reviewsCountAccessibilityLabel"]
            }
            reviews.append(review_data)
        else:
            for value in data.values():
                extract_reviews_data(value, typename, reviews)
    elif isinstance(data, list):
        for item in data:
            extract_reviews_data(item, typename, reviews)

def load_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

def extract_value(data, key):
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key:
                return v
            elif isinstance(v, (dict, list)):
                result = extract_value(v, key)
                if result is not None:
                    return result
    elif isinstance(data, list):
        for item in data:
            result = extract_value(item, key)
            if result is not None:
                return result
    return None

def extract_localized_location(json_data):
    key_to_extract = 'localizedLocation'
    value = extract_value(json_data, key_to_extract)
    return value

def extract_person_capacity(data):
    if isinstance(data, dict):
        if data.get('__typename') == 'PdpEventData':
            return data.get('personCapacity')

        for value in data.values():
            result = extract_person_capacity(value)
            if result is not None:
                return result

    elif isinstance(data, list):
        for item in data:
            result = extract_person_capacity(item)
            if result is not None:
                return result

    return None

async def get_airbnb_data(url):
    print("data")
    try:
        session = AsyncHTMLSession(browser_args=["--no-sandbox", "--disable-setuid-sandbox", "--user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'"])


        response = await session.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Wait for rendering JavaScript
        await response.html.arender()

        # Get the HTML content
        html_content = response.html.html

        # Create BeautifulSoup object
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find the tag with id="data-deferred-state-0"
        tag_data = soup.find('script', id='data-deferred-state-0')
        if tag_data:
            # Extract JSON data from the tag
            json_data = json.loads(tag_data.contents[0])

            # List to store extracted listing titles
            all_listing_titles = []

            #---------------- Fetch Bed Type------------------#
            bedinfo = extract_bed_info(json_data, 'RoomArrangementItem', 'subtitle')

            # ------------------Extract Listing Titles--------------#
            extract_listing_title(json_data, all_listing_titles)

            # ---------------------Fetch Description-------------------#
            # Extract 'title' where '__typename': 'LocationDetail'
            titles = extract_bed_info(json_data, 'Html', 'htmlText')

            # List to store extracted reviews data
            all_reviews_data = []
            
            # ---------------Extract Reviews Data--------------#
            extract_reviews_data(json_data, "PdpReviewsHighlightReviewData", all_reviews_data)

            # -----------------Extract Localized Location------------------#
            localized_location = extract_localized_location(json_data)

            # -------------------Extract Person Capacity-------------------#
            person_capacity = extract_person_capacity(json_data)

            # -------------------Extract Ratings------------------#
            extracted_ratings = {}
            extract_ratings(json_data, extracted_ratings)

            # --------------------Extract Amenities------------------#
            all_amenity_names = []
            extract_amenities(json_data, all_amenity_names)

            #----------------- Extract Host Titles---------------#
            all_host_titles = []
            extract_host_titles(json_data, "PdpHostOverviewDefaultSection", all_host_titles)
            ##for price
            # url = 'https://www.airbnb.com/rooms/581703137932548906?adults=1&category_tag=Tag%3A8678&children=0&enable_m3_private_room=true&infants=0&pets=0&photo_id=1485968494&check_in=2024-03-03&check_out=2024-03-04&source_impression_id=p3_1709403993_j96w%2FPZOVh8MOX1j&previous_page_section_name=1000&federated_search_id=f954c6e9-8940-4636-a73f-ebf334c7df34'
            price= get_airbnb_price(url)


            
            print("Bed Type", bedinfo)
            print("Listing Titles", all_listing_titles)
            print("Description", titles)
            print("Reviews Data",all_reviews_data)
            print("Localized Location",localized_location)
            print("Person Capacity", person_capacity)
            print("Ratings", extracted_ratings)
            print("Amenities", all_amenity_names)
            print("Host Titles", all_host_titles)
            print("Price",price)
    except Exception as e:
        print("Error:", e)
        
    finally:
        await session.close()
        



async def main():
    await url()
df=pd.DataFrame(listing_data)
df.to_csv("AirBnB.csv")
if __name__ == "__main__":
    asyncio.run(main())


