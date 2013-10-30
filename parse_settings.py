import ConfigParser
import ast
import re
import datetime

valid_types = {"any housing":0,
        "apartment":1,
        "condo":2,
        "cottage/cabin":3,
        "duplex":4,
        "flat":5,
        "in-law":7,
        "loft":8,
        "townhouse":9,
        "manufactured":10,
        "assisted living":11,
        "land":12}

def condense_address_query(address):
    condensed_address = re.sub(r' |USA||[A-Z]{2}|,','',address)
    return condensed_address



def default_scraper_settings():
    '''
        Creates dictionary containing the default scraper settings
    '''

    settings = {}
    settings['searchURL'] = "http://sfbay.craigslist.org/search/hhh/eby?catAbb=apa&query=berkeley&zoomToPosting=&minAsk={0}&maxAsk={1}&bedrooms={2}&housing_type={3}&"

    settings['min_price'] = 100
    settings['max_price'] = 10000

    settings['bedrooms'] = 0
    settings['type'] = "any housing"

    settings['max_distance'] = 1.0

    settings['center_address'] = "2520 Channing Way, Berkeley CA 94720"

    settings['max_time'] = "00:20:00"
    settings['start_date'] = 'Oct 26'

    return settings

def parse_settings(settings_file):
    
    settings = default_scraper_settings()

    INT_PARAMS = set(['min_price',
                        'max_price',
			'bedrooms'])

    FLOAT_PARAMS = set(['max_distance'])

    OTHER_PARAMS = set(['center_address',
                        'searchURL',
                        'url_prefix',
                        'max_time'])

    try:
        config = ConfigParser.ConfigParser()
        config.read(settings_file)

        for option in config.options('scraper_settings'):
            if option in FLOAT_PARAMS:
                settings[option] = config.getfloat('scraper_settings',option)
            elif option in INT_PARAMS:
                settings[option] = config.getint('scraper_settings',option)
            elif option in OTHER_PARAMS:
                settings[option] = ast.literal_eval(config.get('scraper_settings',option))

        if settings['type'] not in valid_types:
            print "Invalid housing type in settings file"
            raise Exception

        if type(settings['center_address']) is not str:
            print "Invalid format for center_address"
            raise Exception

        settings['center_address'] = condense_address_query(settings['center_address'])

        if type(settings['searchURL']) is not str:
            print "Invalid search URL"
            raise Exception

        a = re.search(r'\{0\}', settings['searchURL'])
        b = re.search(r'\{1\}', settings['searchURL'])
        c = re.search(r'\{2\}', settings['searchURL'])
        d = re.search(r'\{3\}', settings['searchURL'])

        if not a or not b or not c or not d:
            print "Invalid search URL: Does not have substitutions"
            raise Exception


        if type(settings['max_time']) is str:
            try:
                a = map(int,settings['max_time'].split(':'))
                assert len(a) == 3
                settings['max_time'] = datetime.timedelta(hours=a[0],minutes=a[1],seconds=a[2])
            except:
                print 'max_time does not have the correct format'
                raise Exception
        else:
            print 'max_time does not have the correct format'
            raise Exception

        return settings, settings['searchURL'].format(settings['min_price'],settings['max_price'],
            settings['bedrooms'], valid_types[settings['type']])

    except IOError:
        print 'Invalid settings file path'
        raise Exception
