from enum import Enum


class Regions(Enum):
    g18 = 0
    e113 = 1
    t11n_afr = 2
    t11n_eu = 3
    t18v_c = 4
    t18v_ku = 5


# NOTE: an id field equals to "region.value + 1" is required for
# backward compatibility with the previous Ruby-based implementation.
SATELLITE_REGIONS = {
    Regions.g18: {
        'id': Regions.g18.value + 1,
        'satellite_name': 'Galaxy 18',
        'coverage': 'North America',
        'has_receiver': True
    },
    Regions.e113: {
        'id': Regions.e113.value + 1,
        'satellite_name': 'Eutelsat 113',
        'coverage': 'South America',
        'has_receiver': True
    },
    Regions.t11n_afr: {
        'id': Regions.t11n_afr.value + 1,
        'satellite_name': 'Telstar 11N',
        'coverage': 'Africa',
        'has_receiver': False
    },
    Regions.t11n_eu: {
        'id': Regions.t11n_eu.value + 1,
        'satellite_name': 'Telstar 11N',
        'coverage': 'Europe',
        'has_receiver': False
    },
    Regions.t18v_c: {
        'id': Regions.t18v_c.value + 1,
        'satellite_name': 'Telstar 18V C',
        'coverage': 'Asia Pacific',
        'has_receiver': True
    },
    Regions.t18v_ku: {
        'id': Regions.t18v_ku.value + 1,
        'satellite_name': 'Telstar 18V Ku',
        'coverage': 'Asia Pacific',
        'has_receiver': True
    },
}

all_region_ids = list(region['id'] for region in SATELLITE_REGIONS.values())
all_region_numbers = list(item.value for item in Regions)

# Subset of regions that should confirm rx
monitored_rx_regions = set([
    info['id'] for info in SATELLITE_REGIONS.values() if info['has_receiver']
])

REGION_MASK_ALL_REGIONS = 2**len(SATELLITE_REGIONS) - 1


def region_number_to_id(region_number):
    return SATELLITE_REGIONS[Regions(region_number)]['id']


def region_id_to_number(region_id):
    for region_number, region_detail in SATELLITE_REGIONS.items():
        if region_detail['id'] == region_id:
            return region_number.value


def region_number_list_to_code(order_region_numbers):
    assert (all([x in all_region_numbers for x in order_region_numbers]))
    code = 0
    for region_number in order_region_numbers:
        code |= 1 << region_number
    return code


def region_id_list_to_code(order_region_ids):
    order_region_numbers = [region_id_to_number(x) for x in order_region_ids]
    return region_number_list_to_code(order_region_numbers)


def region_code_to_number_list(code):
    if not code:
        return all_region_numbers
    order_region_numbers = []
    for region in all_region_numbers:
        mask = 1 << region
        if mask & code:
            order_region_numbers.append(region)
    return order_region_numbers


def region_code_to_id_list(code):
    return [region_number_to_id(x) for x in region_code_to_number_list(code)]
