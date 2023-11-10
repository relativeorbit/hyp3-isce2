import numpy as np
from osgeo import gdal

from hyp3_isce2 import water_mask

gdal.UseExceptions()


def test_create_water_mask_with_no_water(tmp_path, test_data_dir):
    input_tif = str(test_data_dir / 'test_geotiff.tif')
    output_tif = str(tmp_path / 'water_mask.tif')
    water_mask.create_water_mask(input_tif, output_tif)

    info = gdal.Info(output_tif, format='json', stats=True)
    assert info['size'] == [20, 20]
    assert info['geoTransform'] == [440720.0, 60.0, 0.0, 3751320.0, 0.0, -60.0]
    assert info['bands'][0]['type'] == 'Byte'
    assert info['bands'][0]['minimum'] == 1
    assert info['bands'][0]['maximum'] == 1
    assert info['bands'][0]['block'] == [256, 256]
    assert info['metadata']['']['AREA_OR_POINT'] == 'Area'
    assert info['metadata']['IMAGE_STRUCTURE']['COMPRESSION'] == 'LZW'


def test_create_water_mask_with_water_and_land(tmp_path, test_data_dir):
    input_tif = str(test_data_dir / 'water_mask_input.tif')
    output_tif = str(tmp_path / 'water_mask.tif')
    water_mask.create_water_mask(input_tif, output_tif)

    info = gdal.Info(output_tif, format='json')
    assert info['geoTransform'] == [200360.0, 80.0, 0.0, 1756920.0, 0.0, -80.0]
    assert info['bands'][0]['type'] == 'Byte'
    assert info['bands'][0]['block'] == [256, 256]
    assert info['metadata']['']['AREA_OR_POINT'] == 'Point'
    assert info['metadata']['IMAGE_STRUCTURE']['COMPRESSION'] == 'LZW'

    ds = gdal.Open(str(output_tif))
    data = ds.GetRasterBand(1).ReadAsArray()
    expected = np.array([
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    ])
    assert np.array_equal(data, expected)
    del ds
