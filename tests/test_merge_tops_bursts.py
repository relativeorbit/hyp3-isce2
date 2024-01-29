"""Tests for hyp3_isce2.merge_tops_bursts module, use single quotes"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import asf_search
import lxml.etree as ET
import numpy as np
import pytest
from requests import Session

import hyp3_isce2.burst as burst_utils
import hyp3_isce2.merge_tops_bursts as merge
from hyp3_isce2 import utils


# TODO combine with test_burst.py's version
def mock_asf_search_results(
    slc_name: str, subswath: str, polarization: str, burst_index: int
) -> asf_search.ASFSearchResults:
    product = asf_search.ASFProduct()
    product.umm = {'InputGranules': [slc_name]}
    product.properties.update(
        {
            'burst': {'subswath': subswath, 'burstIndex': burst_index, 'relativeBurstID': burst_index - 1},
            'polarization': polarization,
            'url': 'https://foo.com/bar/baz.zip',
            'startTime': '2020-06-04T02:22:54.655908Z',
            'pathNumber': 1,
        }
    )
    results = asf_search.ASFSearchResults([product])
    results.searchComplete = True
    return results


@pytest.fixture
def burst_product(test_merge_dir):
    product_path = list(test_merge_dir.glob('*'))[0]
    product = merge.BurstProduct(
        granule='bar',
        reference_date=datetime(2020, 6, 4, 2, 23, 15),
        secondary_date=datetime(2020, 6, 16, 2, 23, 16),
        burst_id=0,
        swath='IW2',
        polarization='VV',
        burst_number=1,
        product_path=product_path,
        n_lines=377,
        n_samples=1272,
        range_looks=20,
        azimuth_looks=4,
        first_valid_line=8,
        n_valid_lines=363,
        first_valid_sample=9,
        n_valid_samples=1220,
        az_time_interval=0.008222225199999992,
        rg_pixel_size=46.59124229430646,
        start_utc=datetime(2020, 6, 4, 2, 22, 54, 655908),
        stop_utc=datetime(2020, 6, 4, 2, 23, 18, 795712),
        relative_orbit=1,
    )
    return product


def test_to_burst_params(burst_product):
    assert burst_product.to_burst_params() == burst_utils.BurstParams('bar', 'IW2', 'VV', 1)


def test_get_burst_metadata(test_merge_dir, burst_product):
    product_path = list(test_merge_dir.glob('*'))[0]

    with patch('hyp3_isce2.merge_tops_bursts.asf_search.granule_search') as mock_search:
        mock_search.return_value = mock_asf_search_results('bar', 'IW2', 'VV', 1)
        product = merge.get_burst_metadata([product_path])[0]
    assert product == burst_product


def test_prep_metadata_dirs(tmp_path):
    annotation_dir, manifest_dir = merge.prep_metadata_dirs(tmp_path)
    assert annotation_dir.is_dir()
    assert manifest_dir.is_dir()


def test_download_metadata_xmls(monkeypatch, tmp_path, test_data_dir):
    params = [burst_utils.BurstParams('foo', 'IW1', 'VV', 1), burst_utils.BurstParams('foo', 'IW2', 'VV', 0)]
    sample_xml = ET.parse(test_data_dir / 'reference_descending.xml').getroot()

    with patch('hyp3_isce2.merge_tops_bursts.burst_utils.get_asf_session') as mock_session:
        with patch('hyp3_isce2.merge_tops_bursts.burst_utils.download_metadata') as mock_download:
            mock_session.return_value = Session()
            mock_download.return_value = sample_xml

            merge.download_metadata_xmls(params, tmp_path)

            assert mock_download.call_count == 1
            assert len(list((tmp_path / 'annotation').glob('*.xml'))) == 2
            assert (tmp_path / 'manifest' / 'foo.xml').exists()


def test_get_scene_roi(tmp_path, test_data_dir):
    s1_obj = utils.load_product(test_data_dir / 'isce2_s1_obj.xml')
    bursts = s1_obj.bursts
    roi = merge.get_scene_roi(bursts)
    golden_roi = (53.045079513806, 27.325111859227817, 54.15684468161031, 27.847161580403135)
    assert np.all(np.isclose(roi, golden_roi))


def test_load_isce_s1_obj(annotation_manifest_dirs):
    annotation_dir, manifest_dir = annotation_manifest_dirs
    s1_obj = merge.load_isce_s1_obj(2, 'VV', annotation_dir.parent)

    assert isinstance(s1_obj, merge.Sentinel1BurstSelect)
    assert s1_obj.swath == 2
    assert s1_obj.polarization == 'vv'
    assert len(s1_obj.tiff) == 1
    assert s1_obj.tiff[0] == ''


def test_Sentinel1BurstSelect(annotation_manifest_dirs, tmp_path, burst_product):
    annotation_dir, manifest_dir = annotation_manifest_dirs
    s1_obj = merge.load_isce_s1_obj(2, 'VV', annotation_dir.parent)

    # Test select_bursts
    test1_obj = deepcopy(s1_obj)
    test1_utc = [burst_product.start_utc]
    test1_obj.select_bursts(test1_utc)
    assert len(test1_obj.product.bursts) == 1
    assert test1_obj.product.numberOfBursts == 1
    assert test1_obj.product.bursts[0].burstStartUTC == test1_utc[0]

    test2_obj = deepcopy(s1_obj)
    test2_utc = [datetime(2020, 6, 4, 2, 22, 57, 414185), datetime(2020, 6, 4, 2, 22, 54, 655908)]
    test2_obj.select_bursts(test2_utc)
    assert len(test2_obj.product.bursts) == 2
    assert test2_obj.product.bursts[0].burstStartUTC < test2_obj.product.bursts[1].burstStartUTC

    # Test update_burst_properties
    test3_obj = deepcopy(test1_obj)
    outpath = tmp_path / 'IW2'
    test3_obj.output = str(outpath)
    test3_obj.update_burst_properties([burst_product])
    assert test3_obj.product.bursts[0].burstNumber == 1
    assert test3_obj.product.bursts[0].firstValidLine == 8
    assert test3_obj.product.bursts[0].numValidLines == 363
    assert test3_obj.product.bursts[0].firstValidSample == 9
    assert test3_obj.product.bursts[0].numValidSamples == 1220
    assert Path(test3_obj.product.bursts[0].image.filename).name == 'burst_01.slc'

    test4_obj = deepcopy(test1_obj)
    bad_product = deepcopy(burst_product)
    bad_product.start_utc = datetime(1999, 1, 1, 1, 0, 0, 0)
    with pytest.raises(ValueError, match='.*do not match.*'):
        test4_obj.update_burst_properties([bad_product])

    # Test write_xml
    test5_obj = deepcopy(test3_obj)
    test5_obj.write_xml()
    assert outpath.with_suffix('.xml').exists()


def test_create_burst_cropped_s1_obj(annotation_manifest_dirs, burst_product):
    s1_obj = merge.create_burst_cropped_s1_obj(2, [burst_product], 'VV', base_dir=annotation_manifest_dirs[0].parent)
    assert isinstance(s1_obj, merge.Sentinel1BurstSelect)
    assert Path(s1_obj.output).with_suffix('.xml').exists()


def test_modify_for_multilook(annotation_manifest_dirs, burst_product):
    s1_obj = merge.create_burst_cropped_s1_obj(2, [burst_product], 'VV', base_dir=annotation_manifest_dirs[0].parent)

    pre_burst = s1_obj.product.bursts[0]
    assert not pre_burst.numberOfSamples == burst_product.n_samples
    assert not pre_burst.numberOfLines == burst_product.n_lines

    burst_product.isce2_burst_number = s1_obj.product.bursts[0].burstNumber
    looked_obj = merge.modify_for_multilook([burst_product], s1_obj)
    burst = looked_obj.product.bursts[0]
    assert burst.numberOfSamples == burst_product.n_samples
    assert burst.numberOfLines == burst_product.n_lines
    assert burst.firstValidSample == burst_product.first_valid_sample
    assert burst.numValidSamples == burst_product.n_valid_samples
    assert burst.firstValidLine == burst_product.first_valid_line
    assert burst.numValidLines == burst_product.n_valid_lines
    assert burst.sensingStop == burst_product.stop_utc
    assert burst.azimuthTimeInterval == burst_product.az_time_interval
    assert burst.rangePixelSize == burst_product.rg_pixel_size
    assert looked_obj.output == 'fine_interferogram/IW2_multilooked'

    bad_product = deepcopy(burst_product)
    bad_product.start_utc = datetime(1999, 1, 1, 1, 0, 0, 0)
    with pytest.raises(ValueError, match='.*do not match.*'):
        looked_obj = merge.modify_for_multilook([bad_product], s1_obj, outdir='foo')
