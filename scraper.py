from bs4 import BeautifulSoup
import re
import argparse
import urllib2
import datetime
import json
import sys
from parse_settings import parse_settings, condense_address_query

reverse_geocoding_baseURL="http://maps.googleapis.com/maps/api/geocode/json?latlng={0},{1}&sensor=false"
directions_baseURL="http://maps.googleapis.com/maps/api/directions/json?origin={0}&destination={1}&mode=walking&sensor=false"

month_mappings = {'Jan':1,
                    'Feb':2,
                    'Mar':3,
                    'Apr':4,
                    'May':5,
                    'Jun':6,
                    'Jul':7,
                    'Aug':8,
                    'Sept':9,
                    'Oct':10,
                    'Nov':11,
                    'Dec':12}

'''
    Converts strings of the format "Oct 26" to datetime.date objects
'''
def convert_date_string(date_string):
    date_string_split = date_string.split()
    return datetime.date(datetime.date.today().year,
                        month_mappings[date_string_split[0]],
                        int(date_string_split[1]))


def get_address_string(latitude,longitude):
    fetch_url = reverse_geocoding_baseURL.format(latitude,longitude)
    maps_address_json = download_page(fetch_url)
    json_decoder = json.JSONDecoder()
    json_parsed = json_decoder.decode(maps_address_json)

    if json_parsed['status'] == 'OK':
        return json_parsed['results'][0]['formatted_address']
    else:
        raise Exception, "Could not get address"

class SearchResult(object):

    def __init__(self,tag,prefix):

        def filter_for_link(tag):
            return tag.name == 'a' and not tag.has_attr("class")

        def filter_for_price(tag):
            return tag.name == 'span' and tag.has_attr("class") and 'price' in tag['class']

        def filter_for_date(tag):
            return tag.name == 'span' and tag.has_attr('class') and 'date' in tag['class']

        self.description = None
        self.bedrooms = None
        self.bathrooms = None
        self.area = None
        self.longitude = None
        self.latitude = None
        self.address = None
        self.distance = None
        self.time = None

        link_tag = tag.find_next(filter_for_link)
        self.url = '{0}{1}'.format(prefix,link_tag["href"].encode('ascii','ignore'))
        self.title = link_tag.contents[0]

        date_string_split = tag.find_next(filter_for_date).contents[0]
        self.date = convert_date_string(date_string_split)

       
        if tag.has_attr('data-longitude') and tag.has_attr('data-latitude'):
            self.longitude = float(tag["data-longitude"])
            self.latitude = float(tag["data-latitude"])
        
        price_string = tag.find_next(filter_for_price).contents[0].encode('ascii','ignore')
        self.price = float(price_string.replace('$',''))

        self.location = None
        try:
            self.location = tag.small.contents
        except AttributeError:
            pass


    '''
        Goes to the page specified by the link for the search result.
        Extracts additional information from this extra page and
            sets additional attributes for the object
        Returns nothing.
    '''
    def parse_additional(self):

        def filter_description(tag):
            return tag.name == 'section' and tag.has_attr('id') and tag['id'] == u'postingbody'

        def filter_content_tags(tag):
            return tag.name == 'span' and tag.has_attr('class') and 'attrbubble' in tag['class']

        detail_page = BeautifulSoup(download_page(self.url))
      
        description_body = detail_page.find(filter_description)
        if description_body is not None:
            description_string = re.sub(r'<br>','',description_body.contents[0])
            self.description = description_string

        tagged_attributes = detail_page.find_all(filter_content_tags)

        for attribute in tagged_attributes:
            attribute_contents = re.sub(r'<b>|</b>|<sup>2</sup>','',''.join(map(str,attribute.contents)))

            m = re.match(r"(?P<bedroom>\w+) / (?P<bathroom>\w+)", attribute_contents)
            if m:
                try:
                    self.bedrooms = int(re.sub(r'BR', '', m.group('bedroom')))
                    self.bathrooms = int(re.sub(r'Ba','',m.group('bathroom')))
                except ValueError:
                    pass

            n = re.match(r"(?P<area>[0-9]+)ft", attribute_contents)
            if n:
                self.area = int(re.sub(r'ft','',n.group('area')))

    '''
        Determines the address of the current search result.
        Uses latitude, longitude, and Google Maps API
    '''
    def determine_address(self):
        if self.address is None:
            try:
                self.address = get_address_string(self.latitude, self.longitude)
                return True
            except:
                return False
        else:
            return True
                
            
            
    '''
        Determines the distance to the current search result from the start point
            specified in address.
        Uses Google Maps API.

        Returns a tuple of the format [distance, datetime.timedelta]
    '''
    def distance_to(self, address):

        if self.distance and self.time:
            return self.distance, self.time
        elif self.determine_address():
            condensed_start_address = condense_address_query(address)
            condensed_dest_address = condense_address_query(self.address)

            directions_url = directions_baseURL.format(condensed_start_address, condensed_dest_address)

            json_directions_unparsed = download_page(directions_url)
            json_decoder = json.JSONDecoder()
            json_directions_parsed = json_decoder.decode(json_directions_unparsed)

            if json_directions_parsed['status'] == 'OK':
                best_route_data = json_directions_parsed['routes'][0]['legs'][0]
                total_meters = int(best_route_data['distance']['value'])
                total_seconds = int(best_route_data['duration']['value'])
                
                total_time = datetime.timedelta(seconds=total_seconds)
                distance_in_miles = total_meters / (1609.34)

                self.distance = distance_in_miles
                self.time = total_time

                return distance_in_miles, total_time
            else:
                return False
        else:
            return False

    '''
        __str__ method for a SearchResult object.
        Does what it's supposed to do.
    '''
    def __str__(self):
        if self.distance and self.time:
            return '{0}: ${1:.2f}, {2} BR, {3} BA, {4} sqft\n{5} mi, {6} hh:mm:ss walking,\n{7}'.format(
                self.title.encode('ascii','ignore'),self.price,self.bedrooms,self.bathrooms,self.area,
                self.distance,self.time,self.url)
        else:
            return '{0}: ${1:.2f}, {2}BR, {3}BA, {4} sqft\n{5}'.format(
                self.title.encode('ascii','ignore'),self.price,self.bedrooms,self.bathrooms,self.area,
                self.url)

    def __eq__(self, other):
        if isinstance(other, SearchResult):
            return self.price == other.price and self.bedrooms == other.bedrooms and self.bathrooms == other.bathrooms and self.latitude == other.latitude and self.longitude == other.longitude
        else:
            return False

    def __ne__(self, other):
        return (not self.__eq__(other))

    def __hash__(self):
        return hash(self.__str__())


def download_page(url):
    response = urllib2.urlopen(url, timeout=5)
    html = response.read()
    return html


def get_search_results(url, start_date):
    html = download_page(url)
    results_url_prefix = url.split('/search')[0]

    def tag_row(tag):
        return tag.name == 'p' and tag.has_attr("class") and unicode('row') in tag['class']

    search_soup = BeautifulSoup(html)
    tags_list = search_soup.find_all(tag_row)
    search_results = []

    if len(tags_list) > 0:
        first_object = SearchResult(tags_list[0], results_url_prefix)
        if first_object.date >= start_date:
            first_object.parse_additional()
            search_results.append(first_object)

            if len(tags_list) > 1:
                next_page_count = 100
                tags_list = tags_list[1:]
                while len(tags_list) != 0 and search_results[0].date >= start_date:
                    for tag in tags_list:
                        search_object = SearchResult(tag, results_url_prefix)
                        if search_object.date >= start_date:
                            search_object.parse_additional()
                            search_results.append(search_object)
                        else:
                            break

                    new_url = '{0}s={1}&'.format(url,next_page_count)
                    search_soup = BeautifulSoup(download_page(new_url))
                    tags_list = search_soup.find_all(tag_row)

                    next_page_count += 100

    return search_results


def remove_duplicates(search_results):
    no_duplicates = []
    for i in range(len(search_results)):
        has_duplicate = False
        for j in range(i+1, len(search_results)):
            if search_results[i] == search_results[j]:
                has_duplicate = True
                break
        if not has_duplicate:
            no_duplicates.append(search_results[i])
    return no_duplicates

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Scrape the East Bay Craigslist for housing in Berkeley")

    parser.add_argument('settings',help='settings file with parameters to scrape for')
    parser.add_argument('-d','--date',type=str,help="start date for listings to search for. Has format mm-dd. If this argument is not included, it will just get today's listings.",default='auto')


    args = parser.parse_args()

    try:
        search_start_date = datetime.date.today()
        if args.date != 'auto':
            date_broken = args.date.split('-')
            month = int(date_broken[0])
            day = int(date_broken[1])
            search_start_date = datetime.date(search_start_date.year,month,day)

        scrape_settings, search_url = parse_settings(args.settings)
        search_url_subbed = search_url.format(scrape_settings['min_price'],
                                    scrape_settings['max_price'],
                                    scrape_settings['bedrooms'],
                                    scrape_settings['type'])
        search_results = get_search_results(search_url_subbed, search_start_date)

        has_distance_filter = lambda x: x.distance_to(scrape_settings['center_address'])
        distance_filter = lambda x: x.distance <= scrape_settings['max_distance'] and x.time <= scrape_settings['max_time']

        filtered_search_results = remove_duplicates(search_results)
        filtered_search_results = filter(has_distance_filter, filtered_search_results)
        filtered_search_results = filter(distance_filter, filtered_search_results)



        for item in filtered_search_results:
            print item
            print '\n'
    except ValueError:
        print 'Please enter a valid date'
        sys.exit(1)
    except Exception:
        print 'Scrape failed'
        sys.exit(1)

