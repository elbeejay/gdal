#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
# $Id$
#
# Project:  GDAL/OGR Test Suite
# Purpose:  Test some PROJ.4 specific translation issues.
# Author:   Frank Warmerdam <warmerdam@pobox.com>
#
###############################################################################
# Copyright (c) 2003, Frank Warmerdam <warmerdam@pobox.com>
# Copyright (c) 2009-2013, Even Rouault <even dot rouault at mines-paris dot org>
# Copyright (c) 2014, Kyle Shannon <kyle at pobox dot com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
###############################################################################

import os
import sys


from osgeo import gdal, osr
import gdaltest
import pytest

###############################################################################
# Return True if proj is at least 4.8.0

have_proj480_flag = None


def have_proj480():

    global have_proj480_flag

    if have_proj480_flag is not None:
        return have_proj480_flag

    try:
        import ctypes
    except ImportError:
        print('cannot find ctypes')
        have_proj480_flag = False
        return have_proj480_flag

    handle = None
    for name in ["libproj.so", "proj.dll", "proj-9.dll", "libproj-0.dll", "libproj-10.dll", "cygproj-10.dll", "libproj.dylib"]:
        try:
            handle = ctypes.cdll.LoadLibrary(name)
        except OSError:
            pass
    if handle is None:
        print('cannot load libproj.so, proj.dll, proj-9.dll, libproj-0.dll, libproj-10.dll, cygproj-10.dll or libproj.dylib')
        have_proj480_flag = False
        return have_proj480_flag

    try:
        handle.pj_init
    except AttributeError:
        print('cannot find pj_init symbol : weird')
        have_proj480_flag = False
        return have_proj480_flag

    # Proj4.8.0 has introduced the pj_etmerc() function. Test for it
    try:
        handle.pj_etmerc
        have_proj480_flag = True
        return have_proj480_flag
    except AttributeError:
        print('cannot find pj_etmerc : PROJ < 4.8.0')
        have_proj480_flag = False
        return have_proj480_flag

###############################################################################
# Test the +k_0 flag works as well as +k when consuming PROJ.4 format.
# This is from Bugzilla bug 355.
#


def test_osr_proj4_1():

    srs = osr.SpatialReference()
    srs.ImportFromProj4('+proj=tmerc +lat_0=53.5000000000 +lon_0=-8.0000000000 +k_0=1.0000350000 +x_0=200000.0000000000 +y_0=250000.0000000000 +a=6377340.189000 +rf=299.324965 +towgs84=482.530,-130.596,564.557,-1.042,-0.214,-0.631,8.15')

    assert abs(srs.GetProjParm(osr.SRS_PP_SCALE_FACTOR) - 1.000035) <= 0.0000005, \
        '+k_0 not supported on import from PROJ.4?'

###############################################################################
# Verify that we can import strings with parameter values that are exponents
# and contain a plus sign.  As per bug 355 in GDAL/OGR's bugzilla.
#


def test_osr_proj4_2():

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=lcc +x_0=0.6096012192024384e+06 +y_0=0 +lon_0=90dw +lat_0=42dn +lat_1=44d4'n +lat_2=42d44'n +a=6378206.400000 +rf=294.978698 +nadgrids=conus,ntv1_can.dat +units=m")

    assert abs(srs.GetProjParm(osr.SRS_PP_FALSE_EASTING) - 609601.219) <= 0.0005, \
        'Parsing exponents not supported?'

    if srs.Validate() != 0:
        print(srs.ExportToPrettyWkt())
        pytest.fail('does not validate')

    
###############################################################################
# Verify that empty srs'es don't cause a crash (#1718).
#


def test_osr_proj4_3():

    srs = osr.SpatialReference()

    try:
        gdal.PushErrorHandler('CPLQuietErrorHandler')
        srs.ExportToProj4()
        gdal.PopErrorHandler()

    except RuntimeError:
        gdal.PopErrorHandler()

    if gdal.GetLastErrorMsg().find('No translation') != -1:
        return

    pytest.fail('empty srs not handled properly')

###############################################################################
# Verify that unrecognized projections return an error, not those
# annoying ellipsoid-only results.
#


def test_osr_proj4_4():

    srs = osr.SpatialReference()
    srs.SetFromUserInput('+proj=utm +zone=11 +datum=WGS84')
    srs.SetAttrValue('PROJCS|PROJECTION', 'FakeTransverseMercator')

    try:
        gdal.PushErrorHandler('CPLQuietErrorHandler')
        srs.ExportToProj4()
        gdal.PopErrorHandler()

    except RuntimeError:
        gdal.PopErrorHandler()

    if gdal.GetLastErrorMsg().find('No translation') != -1:
        return

    pytest.fail('unknown srs not handled properly')

###############################################################################
# Verify that prime meridians are preserved when round tripping. (#1940)
#


def test_osr_proj4_5():

    srs = osr.SpatialReference()

    srs.ImportFromProj4('+proj=lcc +lat_1=46.8 +lat_0=46.8 +lon_0=0 +k_0=0.99987742 +x_0=600000 +y_0=2200000 +a=6378249.2 +b=6356515 +towgs84=-168,-60,320,0,0,0,0 +pm=paris +units=m +no_defs')

    assert abs(float(srs.GetAttrValue('PRIMEM', 1)) - 2.3372291667) <= 0.00000001, \
        'prime meridian lost?'

    assert abs(srs.GetProjParm('central_meridian')) == 0.0, 'central meridian altered?'

    p4 = srs.ExportToProj4()
    srs2 = osr.SpatialReference()
    srs2.ImportFromProj4(p4)

    if not srs.IsSame(srs2):
        gdaltest.post_reason('round trip via PROJ.4 damaged srs?')
        print(srs.ExportToPrettyWkt())
        print(srs2.ExportToPrettyWkt())

    
###############################################################################
# Confirm handling of non-zero latitude of origin mercator (#3026)
#


def test_osr_proj4_6():

    expect_proj4 = '+proj=merc +lon_0=0 +lat_ts=46.1333331 +x_0=1000 +y_0=2000 +datum=WGS84 +units=m +no_defs '

    wkt = """PROJCS["unnamed",
    GEOGCS["WGS 84",
        DATUM["WGS_1984",
            SPHEROID["WGS 84",6378137,298.257223563,
                AUTHORITY["EPSG","7030"]],
            AUTHORITY["EPSG","6326"]],
        PRIMEM["Greenwich",0],
        UNIT["degree",0.0174532925199433],
        AUTHORITY["EPSG","4326"]],
    PROJECTION["Mercator_1SP"],
    PARAMETER["latitude_of_origin",46.1333331],
    PARAMETER["central_meridian",0],
    PARAMETER["scale_factor",1],
    PARAMETER["false_easting",1000],
    PARAMETER["false_northing",2000],
    UNIT["metre",1,
        AUTHORITY["EPSG","9001"]]]"""

    srs = osr.SpatialReference()
    srs.ImportFromWkt(wkt)
    proj4 = srs.ExportToProj4()

    if proj4 != expect_proj4:
        print('Got:', proj4)
        print('Expected:', expect_proj4)
        pytest.fail('Failed to translate non-zero lat-of-origin mercator.')

    # Translate back - should be mercator 1sp

    expect_wkt = """PROJCS["unnamed",
    GEOGCS["WGS 84",
        DATUM["WGS_1984",
            SPHEROID["WGS 84",6378137,298.257223563,
                AUTHORITY["EPSG","7030"]],
            AUTHORITY["EPSG","6326"]],
        PRIMEM["Greenwich",0,
            AUTHORITY["EPSG","8901"]],
        UNIT["degree",0.0174532925199433,
            AUTHORITY["EPSG","9122"]],
        AUTHORITY["EPSG","4326"]],
    PROJECTION["Mercator_2SP"],
    PARAMETER["standard_parallel_1",46.1333331],
    PARAMETER["central_meridian",0],
    PARAMETER["false_easting",1000],
    PARAMETER["false_northing",2000],
    UNIT["Meter",1]]"""

    srs.SetFromUserInput(proj4)
    wkt = srs.ExportToPrettyWkt()
    if wkt != expect_wkt:
        print('Got:   %s' % wkt)
        print('Expect:%s' % expect_wkt)
        pytest.fail('did not get expected mercator_2sp result.')

    
###############################################################################
# Confirm handling of somerc (#3032).
#


def test_osr_proj4_7():

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(23700)

    proj4 = srs.ExportToProj4()
    expected = '+proj=somerc +lat_0=47.14439372222222 +lon_0=19.04857177777778 +k_0=0.99993 +x_0=650000 +y_0=200000 +ellps=GRS67 +towgs84=52.17,-71.82,-14.9,0,0,0,0 +units=m +no_defs '
    if proj4 != expected:
        print('')
        print('Got:     "%s"' % proj4)
        print('Expected:"%s"' % expected)
        pytest.fail('did not get expected proj.4 translation of somerc')

    srs.ImportFromProj4(proj4)

    expected = """PROJCS["unnamed",
    GEOGCS["GRS 67(IUGG 1967)",
        DATUM["unknown",
            SPHEROID["GRS67",6378160,298.247167427],
            TOWGS84[52.17,-71.82,-14.9,0,0,0,0]],
        PRIMEM["Greenwich",0],
        UNIT["degree",0.0174532925199433]],
    PROJECTION["Hotine_Oblique_Mercator_Azimuth_Center"],
    PARAMETER["latitude_of_center",47.14439372222222],
    PARAMETER["longitude_of_center",19.04857177777778],
    PARAMETER["azimuth",90],
    PARAMETER["rectified_grid_angle",90],
    PARAMETER["scale_factor",0.99993],
    PARAMETER["false_easting",650000],
    PARAMETER["false_northing",200000],
    UNIT["Meter",1]]"""

    srs_expected = osr.SpatialReference(wkt=expected)
    if not srs.IsSame(srs_expected):
        print('Got: %s' % srs.ExportToPrettyWkt())
        pytest.fail('did not get expected wkt.')

    
###############################################################################
# Check EPSG:3857, confirm Google Mercator hackery.


def test_osr_proj4_8():

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3857)

    proj4 = srs.ExportToProj4()
    expected = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs'
    assert proj4 == expected, 'did not get expected EPSG:3857 (google mercator) result.'

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3785)

    proj4 = srs.ExportToProj4()
    assert proj4 == expected, 'did not get expected EPSG:3785 (google mercator) result.'

###############################################################################
# NAD27 is a bit special - make sure no towgs84 values come through.
#


def test_osr_proj4_9():

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4267)

    proj4 = srs.ExportToProj4()
    expected = '+proj=longlat +datum=NAD27 +no_defs '
    assert proj4 == expected, 'did not get expected EPSG:4267 (NAD27)'

    srs = osr.SpatialReference()
    srs.SetFromUserInput('NAD27')

    proj4 = srs.ExportToProj4()
    assert proj4 == expected, 'did not get expected "NAD27"'

###############################################################################
# Does geocentric work okay?
#


def test_osr_proj4_10():

    srs = osr.SpatialReference()
    srs.ImportFromProj4('+proj=geocent +ellps=WGS84 +towgs84=0,0,0 ')

    wkt_expected = 'GEOCCS["Geocentric",DATUM["unknown",SPHEROID["WGS84",6378137,298.257223563],TOWGS84[0,0,0,0,0,0,0]],PRIMEM["Greenwich",0]]'

    assert gdaltest.equal_srs_from_wkt(wkt_expected, srs.ExportToWkt()), \
        'did not get expected wkt.'

    p4 = srs.ExportToProj4()
    srs2 = osr.SpatialReference()
    srs2.ImportFromProj4(p4)

    if not srs.IsSame(srs2):
        print(srs.ExportToPrettyWkt())
        print(srs2.ExportToPrettyWkt())
        pytest.fail('round trip via PROJ.4 damaged srs?')

    
###############################################################################
# Test round-tripping of all supported projection methods
#


def test_osr_proj4_11():

    proj4strlist = ['+proj=bonne +lon_0=2 +lat_1=1 +x_0=3 +y_0=4',
                    '+proj=cass +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=nzmg +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=cea +lon_0=2 +lat_ts=1 +x_0=3 +y_0=4',
                    '+proj=tmerc +lat_0=1 +lon_0=2 +k=5 +x_0=3 +y_0=4',
                    '+proj=utm +zone=31 +south',
                    '+proj=merc +lon_0=2 +lat_ts=45 +x_0=3 +y_0=4',
                    '+proj=merc +lon_0=2 +k=5 +x_0=3 +y_0=4',
                    '+proj=stere +lat_0=90 +lat_ts=1 +lon_0=2 +k=2 +x_0=3 +y_0=4',
                    '+proj=stere +lat_0=-90 +lat_ts=-1 +lon_0=2 +k=2 +x_0=3 +y_0=4',
                    '+proj=sterea +lat_0=45 +lon_0=2 +k=2 +x_0=3 +y_0=4',

                    # '+proj=stere +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=eqc +lat_ts=0 +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    # '+proj=eqc +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=gstmerc +lat_0=1 +lon_0=2 +k_0=5 +x_0=3 +y_0=4',
                    '+proj=gnom +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=ortho +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=laea +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=aeqd +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=eqdc +lat_0=1 +lon_0=2 +lat_1=-2 +lat_2=-1 +x_0=3 +y_0=4',
                    '+proj=mill +lat_0=1 +lon_0=2 +x_0=3 +y_0=4 +R_A',
                    '+proj=moll +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=eck1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=eck2 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=eck3 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=eck4 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=eck5 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=eck6 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=poly +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=aea +lat_1=-2 +lat_2=-1 +lat_0=1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=robin +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=vandg +lon_0=2 +x_0=3 +y_0=4 +R_A',
                    '+proj=sinu +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=gall +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=goode +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=igh',
                    '+proj=geos +lon_0=2 +h=1 +x_0=3 +y_0=4',
                    '+proj=lcc +lat_1=1 +lat_0=1 +lon_0=2 +k_0=2 +x_0=3 +y_0=4',
                    '+proj=lcc +lat_1=-10 +lat_2=30 +lat_0=60 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=lcc +lat_1=-10 +lat_2=30 +lat_0=-10 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=omerc +lat_0=1 +lonc=2 +alpha=-1 +k=-3 +x_0=3 +y_0=4 +gamma=-2',
                    '+proj=omerc +lat_0=1 +lon_1=2 +lat_1=3 +lon_2=4 +lat_2=5 +k=-3 +x_0=3 +y_0=4',
                    '+proj=somerc +lat_0=1 +lon_0=2 +k_0=2 +x_0=3 +y_0=4',
                    '+proj=krovak +lat_0=1 +lon_0=2 +alpha=30.28813972222222 +k=2 +x_0=3 +y_0=4',
                    '+proj=imw_p +lat_1=-2 +lat_2=-1 +lon_0=2 +x_0=3 +y_0=4',
                    '+proj=wag1 +x_0=3 +y_0=4',
                    '+proj=wag2 +x_0=3 +y_0=4',
                    '+proj=wag3 +lat_ts=1 +x_0=3 +y_0=4',
                    '+proj=wag4 +x_0=3 +y_0=4',
                    '+proj=wag5 +x_0=3 +y_0=4',
                    '+proj=wag6 +x_0=3 +y_0=4',
                    '+proj=wag7 +x_0=3 +y_0=4',
                    '+proj=tpeqd +lat_1=1 +lon_1=2 +lat_2=3 +lon_2=4 +x_0=5 +y_0=6',

                    '+proj=utm +zone=31 +south +ellps=WGS84 +units=us-ft +no_defs ',
                    '+proj=utm +zone=31 +south +ellps=WGS84 +units=ft +no_defs ',
                    '+proj=utm +zone=31 +south +ellps=WGS84 +units=yd +no_defs ',
                    '+proj=utm +zone=31 +south +ellps=WGS84 +units=us-yd +no_defs ',

                    '+proj=etmerc +lat_0=0 +lon_0=9 +k=0.9996 +units=m +x_0=500000 +datum=WGS84 +no_defs',

                    '+proj=qsc +lat_0=0 +lon_0=0 +ellps=WGS84 +units=m +no_defs ',
                    '+proj=sch +plat_0=1 +plon_0=2 +phdg_0=3 +h_0=4'
                   ]

    for proj4str in proj4strlist:

        # Disabled because proj-4.7.0-4.fc15.x86_64 crashes on that
        if proj4str.find('sterea') != -1 and not have_proj480():
            continue

        srs = osr.SpatialReference()
        if proj4str.find("+no_defs") == -1:
            proj4str = proj4str + " +ellps=WGS84 +units=m +no_defs "
        # print(proj4str)
        srs.ImportFromProj4(proj4str)
        if srs.Validate() != 0:
            print(proj4str)
            print(srs.ExportToPrettyWkt())
            pytest.fail('does not validate')
        out = srs.ExportToProj4()

        assert out == proj4str, 'round trip via PROJ.4 failed'

    
###############################################################################
# Test importing +init=epsg:XXX
#


def test_osr_proj4_12():

    expect_wkt = """GEOGCS["WGS 84",
    DATUM["WGS_1984",
        SPHEROID["WGS 84",6378137,298.257223563,
            AUTHORITY["EPSG","7030"]],
        AUTHORITY["EPSG","6326"]],
    PRIMEM["Greenwich",0,
        AUTHORITY["EPSG","8901"]],
    UNIT["degree",0.0174532925199433,
        AUTHORITY["EPSG","9108"]],
    AUTHORITY["EPSG","4326"]]"""

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+init=epsg:4326")
    wkt = srs.ExportToPrettyWkt()

    if wkt.find("""GEOGCS["WGS 84""") != 0:
        print('Got:%s' % wkt)
        print('Expected:%s' % expect_wkt)
        pytest.fail('Did not get expected result.')

    
###############################################################################
# Test error cases
#


def test_osr_proj4_13():

    proj4strlist = ['',
                    # None,
                    'foo',
                    '+a=5',
                    '+proj=foo',
                    '+proj=longlat +a=5',
                    '+proj=longlat +ellps=wgs72 +towgs84=3']

    gdal.PushErrorHandler('CPLQuietErrorHandler')

    for proj4str in proj4strlist:
        srs = osr.SpatialReference()
        gdal.ErrorReset()
        if srs.ImportFromProj4(proj4str) == 0 and gdal.GetLastErrorMsg() == '':
            gdal.PopErrorHandler()
            pytest.fail()

    gdal.PopErrorHandler()

###############################################################################
# Test etmerc (#4853)
#


def test_osr_proj4_14():

    proj4str = '+proj=etmerc +lat_0=0 +lon_0=9 +k=0.9996 +units=m +x_0=500000 +datum=WGS84 +nodefs'

    # Test importing etmerc
    srs = osr.SpatialReference()
    srs.ImportFromProj4(proj4str)
    wkt = srs.ExportToPrettyWkt()
    expect_wkt = """PROJCS["unnamed",
    GEOGCS["WGS 84",
        DATUM["WGS_1984",
            SPHEROID["WGS 84",6378137,298.257223563,
                AUTHORITY["EPSG","7030"]],
            AUTHORITY["EPSG","6326"]],
        PRIMEM["Greenwich",0,
            AUTHORITY["EPSG","8901"]],
        UNIT["degree",0.0174532925199433,
            AUTHORITY["EPSG","9122"]],
        AUTHORITY["EPSG","4326"]],
    PROJECTION["Transverse_Mercator"],
    PARAMETER["latitude_of_origin",0],
    PARAMETER["central_meridian",9],
    PARAMETER["scale_factor",0.9996],
    PARAMETER["false_easting",500000],
    PARAMETER["false_northing",0],
    UNIT["Meter",1],
    EXTENSION["PROJ4","+proj=etmerc +lat_0=0 +lon_0=9 +k=0.9996 +units=m +x_0=500000 +datum=WGS84 +nodefs"]]"""
    if wkt != expect_wkt:
        print('Got:%s' % wkt)
        print('Expected:%s' % expect_wkt)
        pytest.fail('Did not get expected result.')

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32600 + 32)

    # Test exporting standard Transverse_Mercator, without any particular option
    proj4str = srs.ExportToProj4()
    expect_proj4str = '+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs '
    if proj4str != expect_proj4str:
        print('Got:%s' % proj4str)
        print('Expected:%s' % expect_proj4str)
        pytest.fail('Did not get expected result.')

    # Test exporting standard Transverse_Mercator, with OSR_USE_ETMERC=YES
    gdal.SetConfigOption('OSR_USE_ETMERC', 'YES')
    proj4str = srs.ExportToProj4()
    gdal.SetConfigOption('OSR_USE_ETMERC', None)
    expect_proj4str = '+proj=etmerc +lat_0=0 +lon_0=9 +k=0.9996 +x_0=500000 +y_0=0 +datum=WGS84 +units=m +no_defs '
    if proj4str != expect_proj4str:
        print('Got:%s' % proj4str)
        print('Expected:%s' % expect_proj4str)
        pytest.fail('Did not get expected result.')

    # Test exporting standard Transverse_Mercator, with OSR_USE_ETMERC=NO
    gdal.SetConfigOption('OSR_USE_ETMERC', 'NO')
    proj4str = srs.ExportToProj4()
    gdal.SetConfigOption('OSR_USE_ETMERC', None)
    expect_proj4str = '+proj=tmerc +lat_0=0 +lon_0=9 +k=0.9996 +x_0=500000 +y_0=0 +datum=WGS84 +units=m +no_defs '
    if proj4str != expect_proj4str:
        print('Got:%s' % proj4str)
        print('Expected:%s' % expect_proj4str)
        pytest.fail('Did not get expected result.')

    
###############################################################################
# Test other authorities than EPSG, e.g. IGNF:XXXX
#


def test_osr_proj4_15():

    srs = osr.SpatialReference()
    if srs.ImportFromProj4("+init=IGNF:LAMB93") != 0:
        pytest.skip()

    assert srs.GetAuthorityName(None) == 'IGNF' and srs.GetAuthorityCode(None) == 'LAMB93'

    assert srs.Validate() == 0

###############################################################################
# Test unit parsing
#


def test_osr_proj4_16():

    def almost(a, b):
        if abs(a - b) > 0.000000000001:
            return False
        return True
    units = (('km', 1000.),
             ('m', 1.),
             ('dm', 1. / 10.),
             ('cm', 1. / 100.),
             ('mm', 1. / 1000.),
             ('kmi', 1852.0),
             ('in', 0.0254),
             ('ft', 0.3048),
             ('yd', 0.9144),
             ('mi', 1609.344),
             ('fath', 1.8288),
             ('ch', 20.1168),
             ('link', 0.201168),
             ('us-in', 1. / 39.37),
             ('us-ft', 0.304800609601219),
             ('us-yd', 0.914401828803658),
             ('us-ch', 20.11684023368047),
             ('us-mi', 1609.347218694437),
             ('ind-yd', 0.91439523),
             ('ind-ft', 0.30479841),
             ('ind-ch', 20.11669506))

    srs = osr.SpatialReference()
    for u in units:
        assert srs.ImportFromProj4('+proj=utm +zone=11 +datum=WGS84 +units=%s' % u[0]) == 0
        to_met = srs.GetLinearUnits()
        assert almost(to_met, u[1]), \
            ('Did not get expected units: %s vs %s' % (str(u), str(to_met)))
    
###############################################################################
# Test unit parsing for name assignment
#


def test_osr_proj4_17():

    units = (('km', 'kilometre'),
             ('m', 'Meter'),
             ('dm', 'Decimeter'),
             ('cm', 'Centimeter'),
             ('mm', 'Millimeter'),
             ('kmi', 'Nautical_Mile_International'),
             ('in', 'Inch_International'),
             ('ft', 'Foot (International)'),
             ('yd', 'Yard_International'),
             ('mi', 'Statute_Mile_International'),
             ('fath', 'Fathom_International'),
             ('ch', 'Chain_International'),
             ('link', 'Link_International'),
             ('us-in', 'Inch_US_Surveyor'),
             ('us-ft', 'Foot_US'),
             ('us-yd', 'Yard_US_Surveyor'),
             ('us-ch', 'Chain_US_Surveyor'),
             ('us-mi', 'Statute_Mile_US_Surveyor'),
             ('ind-yd', 'Yard_Indian'),
             ('ind-ft', 'Foot_Indian'),
             ('ind-ch', 'Chain_Indian'))

    srs = osr.SpatialReference()
    for u in units:
        assert srs.ImportFromProj4('+proj=utm +zone=11 +datum=WGS84 +units=%s' % u[0]) == 0
        unit_name = srs.GetLinearUnitsName()
        assert unit_name == u[1], \
            ('Did not get expected unit name: %s vs %s' % (str(u), str(unit_name)))
    
###############################################################################
# Test fix for #5511
#


def test_osr_proj4_18():

    for p in ['no_off', 'no_uoff']:
        srs = osr.SpatialReference()
        srs.ImportFromProj4('+proj=omerc +lat_0=57 +lonc=-133 +alpha=-36 +k=0.9999 +x_0=5000000 +y_0=-5000000 +%s +datum=NAD83 +units=m +no_defs' % p)
        if srs.Validate() != 0:
            print(srs.ExportToPrettyWkt())
            pytest.fail('does not validate')
        out = srs.ExportToProj4()
        proj4str = '+proj=omerc +lat_0=57 +lonc=-133 +alpha=-36 +k=0.9999 +x_0=5000000 +y_0=-5000000 +no_uoff +gamma=-36 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs '
        if out != proj4str:
            print(p)
            pytest.fail('round trip via PROJ.4 failed')

    
###############################################################################
# Test EXTENSION and AUTHORITY in DATUM


def test_osr_proj4_19():

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=longlat +datum=WGS84 +nadgrids=@null")

    assert srs.ExportToWkt() == 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],EXTENSION["PROJ4_GRIDS","@null"],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]'

    if srs.Validate() != 0:
        print(srs.ExportToPrettyWkt())
        pytest.fail('does not validate')

    
###############################################################################
# Test EXTENSION in GOGCS


def test_osr_proj4_20():

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=longlat +foo=bar +wktext")

    assert (srs.ExportToWkt() == 'GEOGCS["WGS 84",DATUM["unknown",SPHEROID["WGS84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],EXTENSION["PROJ4","+proj=longlat +foo=bar +wktext"]]' or \
       srs.ExportToWkt() == 'GEOGCS["unnamed ellipse",DATUM["unknown",SPHEROID["unnamed",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],EXTENSION["PROJ4","+proj=longlat +foo=bar +wktext"]]')

    if srs.Validate() != 0:
        print(srs.ExportToPrettyWkt())
        pytest.fail('does not validate')

    
###############################################################################
# Test importing datum other than WGS84, WGS72, NAD27 or NAD83


def test_osr_proj4_21():

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=longlat +datum=nzgd49")

    gdal.SetConfigOption('OVERRIDE_PROJ_DATUM_WITH_TOWGS84', 'NO')
    got = srs.ExportToProj4()
    gdal.SetConfigOption('OVERRIDE_PROJ_DATUM_WITH_TOWGS84', None)

    assert got.find('+proj=longlat +datum=nzgd49') == 0

###############################################################################
# Test importing ellipsoid defined with +R


def test_osr_proj4_22():

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=longlat +R=1")
    got = srs.ExportToProj4()

    assert got.find('+proj=longlat +a=1 +b=1') == 0

###############################################################################
# Test importing ellipsoid defined with +a and +f


def test_osr_proj4_23():

    # +f=0 particular case
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=longlat +a=1 +f=0")
    got = srs.ExportToProj4()

    assert got.find('+proj=longlat +a=1 +b=1') == 0

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=longlat +a=2 +f=0.5")
    got = srs.ExportToProj4()

    assert got.find('+proj=longlat +a=2 +b=1') == 0

###############################################################################
# Test importing linear units defined with +to_meter


def test_osr_proj4_24():

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +to_meter=1.0")
    got = srs.ExportToProj4()

    assert got.find('+units=m') >= 0

    # Intl foot
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +to_meter=0.3048")
    got = srs.ExportToProj4()

    assert got.find('+units=ft') >= 0

    # US foot
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +to_meter=0.3048006096012192")
    got = srs.ExportToProj4()

    assert got.find('+units=us-ft') >= 0

    # unknown
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +to_meter=0.4")
    got = srs.ExportToProj4()

    assert got.find('+to_meter=0.4') >= 0

###############################################################################
# Test importing linear units defined with +vto_meter


def test_osr_proj4_25():

    if not have_proj480():
        pytest.skip()

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +geoidgrids=foo +vto_meter=1.0")
    got = srs.ExportToProj4()

    assert got.find('+vunits=m') >= 0

    # Intl foot
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +geoidgrids=foo +vto_meter=0.3048")
    got = srs.ExportToProj4()

    assert got.find('+vunits=ft') >= 0

    # US foot
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +geoidgrids=foo +vto_meter=0.3048006096012192")
    got = srs.ExportToProj4()

    assert got.find('+vunits=us-ft') >= 0

    # Unknown
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +geoidgrids=foo +vto_meter=0.4")
    got = srs.ExportToProj4()

    assert got.find('+vto_meter=0.4') >= 0

###############################################################################
# Test importing linear units defined with +vunits


def test_osr_proj4_26():

    if not have_proj480():
        pytest.skip()

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +geoidgrids=foo +vunits=m")
    got = srs.ExportToProj4()

    assert got.find('+vunits=m') >= 0

    # Intl foot
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +geoidgrids=foo +vunits=ft")
    got = srs.ExportToProj4()

    assert got.find('+vunits=ft') >= 0

    # US yard
    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=merc +geoidgrids=foo +vunits=us-yd")
    got = srs.ExportToProj4()

    assert got.find('+vunits=us-yd') >= 0

###############################################################################
# Test geostationary +sweep (#6030)


def test_osr_proj4_27():

    if not have_proj480():
        pytest.skip()

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+proj=geos +h=35785831 +lon_0=0 +datum=WGS84 +sweep=x +units=m")
    got = srs.ExportToProj4()

    assert got.find('+proj=geos +h=35785831 +lon_0=0 +datum=WGS84 +sweep=x +units=m') >= 0

###############################################################################
# Test importing +init=epsg: with an override


def test_osr_proj4_28():

    srs = osr.SpatialReference()
    srs.ImportFromProj4("+init=epsg:32631 +units=cm")
    got = srs.ExportToWkt()

    assert got.find('32631') < 0


def test_osr_proj4_28_missing_proj_epsg_dict():

    python_exe = sys.executable
    if sys.platform == 'win32':
        python_exe = python_exe.replace('\\', '/')

    ret = gdaltest.runexternal(python_exe + ' osr_proj4.py osr_proj4_28')
    assert ret.find('fail') < 0


def test_osr_proj4_error_cases_export_mercator():

    srs = osr.SpatialReference()

    # latitude_of_origin != 0.0 and scale != 1.0
    srs.SetMercator(30.0, 0.0, 0.99, 0.0, 0.0)
    with gdaltest.error_handler():
        got = srs.ExportToProj4()
    assert got == ''

    # latitude_of_origin != 0.0
    srs.SetMercator2SP(0.0, 40.0, 0.0, 0.0, 0.0)
    with gdaltest.error_handler():
        got = srs.ExportToProj4()
    assert got == ''


gdaltest_list = [
    test_osr_proj4_1,
    test_osr_proj4_2,
    test_osr_proj4_3,
    test_osr_proj4_4,
    test_osr_proj4_5,
    test_osr_proj4_6,
    test_osr_proj4_7,
    test_osr_proj4_8,
    test_osr_proj4_9,
    test_osr_proj4_10,
    test_osr_proj4_11,
    test_osr_proj4_12,
    test_osr_proj4_13,
    test_osr_proj4_14,
    test_osr_proj4_15,
    test_osr_proj4_16,
    test_osr_proj4_17,
    test_osr_proj4_18,
    test_osr_proj4_19,
    test_osr_proj4_20,
    test_osr_proj4_21,
    test_osr_proj4_22,
    test_osr_proj4_23,
    test_osr_proj4_24,
    test_osr_proj4_25,
    test_osr_proj4_26,
    test_osr_proj4_27,
    test_osr_proj4_28,
    test_osr_proj4_28_missing_proj_epsg_dict,
    test_osr_proj4_error_cases_export_mercator,
]


if __name__ == '__main__':

    if len(sys.argv) == 2 and sys.argv[1] == "osr_proj4_28":
        os.putenv('PROJ_LIB', '/i/dont_exist')
        gdaltest.run_tests([test_osr_proj4_28])
        sys.exit(0)

    gdaltest.setup_run('osr_proj4')

    gdaltest.run_tests(gdaltest_list)

    sys.exit(gdaltest.summarize())
