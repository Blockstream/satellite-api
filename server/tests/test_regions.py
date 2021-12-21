import pytest
import regions


def test_region_list_to_code():
    assert regions.region_list_to_code([]) == 0x0
    assert regions.region_list_to_code([0, 1, 2, 3, 4,
                                        5]) == regions.REGION_MASK_ALL_REGIONS
    assert regions.region_list_to_code([0, 2, 4]) == 0x15
    assert regions.region_list_to_code([1, 3, 5]) == 0x2A
    with pytest.raises(AssertionError):
        regions.region_list_to_code([1, 6])


def test_region_code_to_id_list():
    assert regions.region_code_to_id_list(0x0) == regions.all_region_ids
    assert regions.region_code_to_id_list(None) == regions.all_region_ids
    assert regions.region_code_to_id_list(
        regions.REGION_MASK_ALL_REGIONS) == regions.all_region_ids
    assert regions.region_code_to_id_list(0x15) == [
        regions.SATELLITE_REGIONS[regions.Regions.g18]['id'],
        regions.SATELLITE_REGIONS[regions.Regions.t11n_afr]['id'],
        regions.SATELLITE_REGIONS[regions.Regions.t18v_c]['id']
    ]
    assert regions.region_code_to_id_list(0x2A) == [
        regions.SATELLITE_REGIONS[regions.Regions.e113]['id'],
        regions.SATELLITE_REGIONS[regions.Regions.t11n_eu]['id'],
        regions.SATELLITE_REGIONS[regions.Regions.t18v_ku]['id']
    ]


def test_region_code_to_number_list():
    assert regions.region_code_to_number_list(
        0x0) == regions.all_region_numbers
    assert regions.region_code_to_number_list(
        None) == regions.all_region_numbers
    assert regions.region_code_to_number_list(
        regions.REGION_MASK_ALL_REGIONS) == regions.all_region_numbers
    assert regions.region_code_to_number_list(0x15) == [
        regions.Regions.g18.value, regions.Regions.t11n_afr.value,
        regions.Regions.t18v_c.value
    ]
    assert regions.region_code_to_number_list(0x2A) == [
        regions.Regions.e113.value, regions.Regions.t11n_eu.value,
        regions.Regions.t18v_ku.value
    ]
