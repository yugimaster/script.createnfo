# -*- coding: utf8 -*-
# Python script for creating .nfo files for movies/tvshows/musicvideos/music in Kodi
# When use gevent you need install gevent first

import gevent
from gevent import monkey
monkey.patch_all()
import json
import urllib
import urllib2
import gzip
import StringIO
import re
import os
import datetime
from lxml import etree

SERVER = "http://tv.t002.ottcn.com/i-tvbin/qtv_video"
QUA = urllib.quote_plus("QV=1&VN=1.1.27&PT=PVS&RL=1920x1080&IT=12117592000&OS=1.1.27&CHID=13032&DV=tencent_macaroni")
totaltime_videodetail = 0


def GetHttpData(url, data=None, cookie=None, headers=None):
    try:
        req = urllib2.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) {0}{1}'.
                       format('AppleWebKit/537.36 (KHTML, like Gecko) ',
                              'Chrome/28.0.1500.71 Safari/537.36'))
        req.add_header('Accept-encoding', 'gzip')
        if cookie is not None:
            req.add_header('Cookie', cookie)
        if headers is not None:
            for header in headers:
                req.add_header(header, headers[header])
        if data:
            if isinstance(data, dict):
                data = urllib.urlencode(data)
            response = urllib2.urlopen(req, data, timeout=3)
        else:
            response = urllib2.urlopen(req, timeout=3)
        httpdata = response.read()
        if response.headers.get('content-encoding', None) == 'gzip':
            httpdata = gzip.GzipFile(fileobj=StringIO.StringIO(httpdata)).read()
        response.close()
        match = re.compile('encoding=(.+?)"').findall(httpdata)
        if not match:
            match = re.compile('meta charset="(.+?)"').findall(httpdata)
        if match:
            charset = match[0].lower()
            if (charset != 'utf-8') and (charset != 'utf8'):
                httpdata = unicode(httpdata, charset).encode('utf8')
    except Exception:
        httpdata = '{"status": "Fail"}'
    return httpdata


class TencentVideo(object):
    """docstring for RenRenMeiJu"""
    def __init__(self):
        pass

    def get_json(self, url, data=None, pretty=False):
        s = json.loads(GetHttpData(url, data=data))
        if pretty:
            print json.dumps(s, sort_keys=True,
                             indent=4, separators=(',', ': '))
        return s

    def index(self):
        API = '/channel_list/get_channel_list?tv_cgi_ver={0}&format={1}&req_from={2}&channel_types={3}&Q-UA={4}'.format("1.0", "json", "PVS_APK", "all", QUA)
        return self.get_json(SERVER + API)

    def video_detail(self, cid):
        API = '/cover_details/get_cover_basic?tv_cgi_ver=1.0&format=json&req_from=PVS_APK&start_type=head&video_num=0&video_filter=all&cid={0}&Q-UA={1}'.format(cid, QUA)
        return self.get_json(SERVER + API)

    def filter_list(self, channel):
        API = '/channel_filter/get_filter?tv_cgi_ver=1.0&format=json&req_from=PVS_APK&channel_selector={0}&filter_selector=single&Q-UA={1}'.format(channel, QUA)
        return self.get_json(SERVER + API)

    def channel_list(self, channel, route, sort, filter_name, settype, page, pagenum):
        API = '/video_list/get_video_list?platform=8&site={site}&filter={filter}&list_route_type={route}&sortby={sort}&fieldset={settype}&page={page}&pagesize={pagenum}&otype=json&Q-UA={QUA}'
        API = API.format(
            site=channel,
            filter=filter_name,
            route=route,
            settype=settype,
            sort=sort,
            page=page,
            pagenum=pagenum,
            QUA=QUA)
        return self.get_json(SERVER + API)


def GetFilterList(channel_id):
    data = TencentVideo().filter_list(channel_id)
    filter_list = data['data']['channel_filters'][0]['single_filter']['filters']
    return filter_list


def GetChannelList(channel_id, route, sortby, filter_name, select_type, page, pagenum):
    data = TencentVideo().channel_list(channel_id, route, sortby, filter_name, select_type, page, pagenum)
    try:
        channel_list = data['data']['infos']
    except Exception:
        channel_list = []
    return channel_list


def GetVideoList():
    threads = []
    data = TencentVideo().index()
    channels = data['data']['channels']
    for channel in channels:
        if channel['type'] != "1" or channel['channel_id'] == "auto":
            continue
        if channel['channel_id'] != "tv":
            continue
        channel_id = channel['channel_id']
        filters = GetFilterList(channel_id)
        select_type = channel['select_type']
        for item in filters:
            channel_list = []
            first_list = GetChannelList(channel_id, item['list_route_type'], item['sortby'], item['pattern'], select_type, 0, 30)
            channel_list.extend(first_list)
            second_list = GetChannelList(channel_id, item['list_route_type'], item['sortby'], item['pattern'], select_type, 1, 30)
            channel_list.extend(second_list)
            for listitem in channel_list:
                title = listitem.get("title")
                cid = listitem.get("id")
                print title
                print channel_id
                if channel_id == "movie":
                    threads.append(gevent.spawn(SaveMovieFiles, cid, item['chi_name']))
                elif channel_id == "tv":
                    threads.append(gevent.spawn(SaveTVShowFiles, cid, item['chi_name']))
    gevent.joinall(threads)


def GetVideoDetail(cid):
    t0 = datetime.datetime.now()
    data = TencentVideo().video_detail(cid)
    t1 = datetime.datetime.now()
    global totaltime_videodetail
    totaltime_videodetail += (t1 - t0).total_seconds()
    return data


def SaveMovieFiles(cid, filter_name):
    data = GetVideoDetail(cid)
    data = data.get("data")
    if not data:
        return
    title = data.get("title")
    file_path = "C:\\xbmc-workspace\\LocalDB\\Movies\\"
    strm_path = file_path + title + ".strm"
    nfo_path = file_path + title + ".nfo"
    if os.path.exists(strm_path) and os.path.exists(nfo_path):
        return
    with open(strm_path, "w+") as f1, open(nfo_path, "w+") as f2:
        f1.write("playvideo")
        CreateMovieNfoFiles(data, filter_name, f2)


def SaveTVShowFiles(cid, filter_name):
    data = GetVideoDetail(cid)
    data = data.get("data")
    if not data:
        return
    title = data.get("title")
    file_path = "C:\\xbmc-workspace\\LocalDB\\TVShows\\" + title
    if os.path.exists(file_path):
        return
    os.mkdir(file_path)
    strm_path = file_path + "\\tvshow.strm"
    nfo_path = file_path + "\\tvshow.nfo"
    if os.path.exists(strm_path) and os.path.exists(nfo_path):
        return
    with open(strm_path, "w+") as f1, open(nfo_path, "w+") as f2:
        f1.write("playvideo")
        CreateTVShowNfoFiles(data, filter_name, f2)


def CreateMovieNfoFiles(movie_item, filter_name, nfo_file):
    title = movie_item.get("title")
    # movie *.nfo file
    root = etree.Element("movie")
    # tag title
    xtitle = etree.Element("title")
    xtitle.text = title
    root.append(xtitle)
    # tag originaltitle
    xoriginaltitle = etree.Element("originaltitle")
    xoriginaltitle.text = ""
    root.append(xoriginaltitle)
    # tag sorttitle
    xsorttitle = etree.Element("sorttitle")
    xsorttitle.text = title
    root.append(xsorttitle)
    # tag set
    xset = etree.Element("set")
    xset.text = ""
    root.append(xset)
    # tag ratings
    xrating = etree.Element("rating")
    xrating.text = movie_item.get("score")
    root.append(xrating)
    # tag year
    xyear = etree.Element("year")
    xyear.text = movie_item.get("year")
    root.append(xyear)
    # tag top250
    xtop250 = etree.Element("top250")
    xtop250.text = ""
    root.append(xtop250)
    # tag votes
    xvotes = etree.Element("votes")
    xvotes.text = ""
    root.append(xvotes)
    # tag outline
    xoutline = etree.Element("outline")
    xoutline.text = movie_item.get("s_title")
    root.append(xoutline)
    # tag plot
    xplot = etree.Element("plot")
    xplot.text = movie_item.get("c_description")
    root.append(xplot)
    # tag tagline
    xtagline = etree.Element("tagline")
    xtagline.text = ""
    root.append(xtagline)
    # tag runtime
    xruntime = etree.Element("runtime")
    xruntime.text = ""
    root.append(xruntime)
    # tag thumb
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = movie_item['cover_pictures'].get("pic_770x1080")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="fanart")
    xthumb.text = movie_item['cover_pictures'].get("pic_1920x1080")
    root.append(xthumb)
    xthumb = etree.Element("thumb")
    xthumb.text = movie_item['cover_pictures'].get("pic_260x364")
    root.append(xthumb)
    xthumb = etree.Element("thumb")
    xthumb.text = movie_item['cover_pictures'].get("pic_350x490")
    root.append(xthumb)
    xthumb = etree.Element("thumb")
    xthumb.text = movie_item['cover_pictures'].get("pic_408x230")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="landscape")
    xthumb.text = movie_item['cover_pictures'].get("pic_498x280")
    root.append(xthumb)
    # tag poster
    xposter = etree.Element("poster")
    xthumb = etree.SubElement(xposter, "thumb")
    xthumb.text = movie_item['cover_pictures'].get("pic_350x490")
    root.append(xposter)
    # tag landscape
    xlandscape = etree.Element("landscape")
    xthumb = etree.SubElement(xlandscape, "thumb")
    xthumb.text = movie_item['cover_pictures'].get("pic_498x280")
    root.append(xlandscape)
    # tag fanart
    xfanart = etree.Element("fanart")
    xthumb = etree.SubElement(xfanart, "thumb")
    xthumb.text = movie_item['cover_pictures'].get("pic_1920x1080")
    root.append(xfanart)
    # tag mpaa
    xmpaa = etree.Element("mpaa")
    xmpaa.text = ""
    root.append(xmpaa)
    # tag playcount
    xplaycount = etree.Element("playcount")
    root.append(xplaycount)
    # tag id
    xid = etree.Element("id")
    xid.text = movie_item.get("c_id")
    root.append(xid)
    # tag filenameandpath
    xpath = etree.Element("filenameandpath")
    xpath.text = ""
    root.append(xpath)
    # tag trailer
    xtrailer = etree.Element("trailer")
    xtrailer.text = ""
    root.append(xtrailer)
    # tag genre
    xgenre = etree.Element("genre")
    xgenre.text = filter_name
    root.append(xgenre)
    # tag country
    xcountry = etree.Element("country")
    xcountry.text = movie_item.get("area_name")
    root.append(xcountry)
    # tag credits
    xcredits = etree.Element("credits")
    xcredits.text = ""
    root.append(xcredits)
    # tag fileinfo
    xfileinfo = etree.Element("fileinfo")
    xfileinfo.text = ""
    root.append(xfileinfo)
    # tag studio
    xstudio = etree.Element("studio")
    xstudio.text = ""
    root.append(xstudio)
    # tag director
    director_list = movie_item.get("directors")
    for item in director_list:
        xdirector = etree.Element("director")
        xdirector.text = item
        root.append(xdirector)
    # tag actor
    actor_list = movie_item.get("leading_actors")
    for item in actor_list:
        xactor = etree.Element("actor")
        xname = etree.SubElement(xactor, "name")
        xname.text = item
        xrole = etree.SubElement(xactor, "role")
        xrole.text = ""
        root.append(xactor)
    nfo_file.write(etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))


def CreateTVShowNfoFiles(tv_item, filter_name, nfo_file):
    title = tv_item.get("title")
    # tvshow *.nfo file
    root = etree.Element("tvshow")
    # tag title
    xtitle = etree.Element("title")
    xtitle.text = title
    root.append(xtitle)
    # tag showtitle
    xshowtitle = etree.Element("showtitle")
    root.append(xshowtitle)
    # tag sorttitle
    xsorttitle = etree.Element("sorttitle")
    xsorttitle.text = title
    root.append(xsorttitle)
    # tag set
    xset = etree.Element("set")
    root.append(xset)
    # tag ratings
    xrating = etree.Element("rating")
    xrating.text = tv_item.get("score")
    root.append(xrating)
    # tag year
    xyear = etree.Element("year")
    xyear.text = tv_item.get("year")
    root.append(xyear)
    # tag top250
    xtop250 = etree.Element("top250")
    root.append(xtop250)
    # tag season
    xseason = etree.Element("season")
    root.append(xseason)
    # tag episode
    xepisode = etree.Element("episode")
    root.append(xepisode)
    # tag displayseason
    xdisplayseason = etree.Element("displayseason")
    xdisplayseason.text = tv_item.get("episode_all")
    root.append(xdisplayseason)
    # tag displayepisode
    xdisplayepisode = etree.Element("displayepisode")
    xdisplayepisode.text = str(tv_item.get("video_num"))
    root.append(xdisplayepisode)
    # tag votes
    xvotes = etree.Element("votes")
    root.append(xvotes)
    # tag outline
    xoutline = etree.Element("outline")
    xoutline.text = tv_item.get("s_title")
    root.append(xoutline)
    # tag plot
    xplot = etree.Element("plot")
    xplot.text = tv_item.get("c_description")
    root.append(xplot)
    # tag tagline
    xtagline = etree.Element("tagline")
    root.append(xtagline)
    # tag runtime
    xruntime = etree.Element("runtime")
    root.append(xruntime)
    # tag thumb
    xthumb = etree.Element("thumb")
    xthumb.text = tv_item['cover_pictures'].get("pic_770x1080")
    root.append(xthumb)
    xthumb = etree.Element("thumb")
    xthumb.text = tv_item['cover_pictures'].get("pic_1920x1080")
    root.append(xthumb)
    xthumb = etree.Element("thumb")
    xthumb.text = tv_item['cover_pictures'].get("pic_260x364")
    root.append(xthumb)
    xthumb = etree.Element("thumb")
    xthumb.text = tv_item['cover_pictures'].get("pic_350x490")
    root.append(xthumb)
    xthumb = etree.Element("thumb")
    xthumb.text = tv_item['cover_pictures'].get("pic_408x230")
    root.append(xthumb)
    xthumb = etree.Element("thumb")
    xthumb.text = tv_item['cover_pictures'].get("pic_498x280")
    root.append(xthumb)
    # tag poster
    xposter = etree.Element("poster")
    xposter.text = tv_item['cover_pictures'].get("pic_350x490")
    root.append(xposter)
    # tag landscape
    xlandscape = etree.Element("landscape")
    xlandscape.text = tv_item['cover_pictures'].get("pic_498x280")
    root.append(xlandscape)
    # tag fanart
    xfanart = etree.Element("fanart")
    xfanart.text = tv_item['cover_pictures'].get("pic_1920x1080")
    root.append(xfanart)
    # tag mpaa
    xmpaa = etree.Element("mpaa")
    root.append(xmpaa)
    # tag playcount
    xplaycount = etree.Element("playcount")
    root.append(xplaycount)
    # tag id
    xid = etree.Element("id")
    xid.text = tv_item.get("c_id")
    root.append(xid)
    # tag filenameandpath
    xpath = etree.Element("filenameandpath")
    root.append(xpath)
    # tag trailer
    xtrailer = etree.Element("trailer")
    root.append(xtrailer)
    # tag genre
    xgenre = etree.Element("genre")
    xgenre.text = filter_name
    root.append(xgenre)
    # tag country
    xcountry = etree.Element("country")
    xcountry.text = tv_item.get("area_name")
    root.append(xcountry)
    # tag premiered
    xpremiered = etree.Element("premiered")
    xpremiered.text = tv_item.get("publish_date")
    root.append(xpremiered)
    # tag credits
    xcredits = etree.Element("credits")
    root.append(xcredits)
    # tag fileinfo
    xfileinfo = etree.Element("fileinfo")
    root.append(xfileinfo)
    # tag studio
    xstudio = etree.Element("studio")
    root.append(xstudio)
    # tag director
    director_list = tv_item.get("directors")
    for item in director_list:
        xdirector = etree.Element("director")
        xdirector.text = item
        root.append(xdirector)
    # tag actor
    actor_list = tv_item.get("leading_actors")
    for item in actor_list:
        xactor = etree.Element("actor")
        xname = etree.SubElement(xactor, "name")
        xname.text = item
        xrole = etree.SubElement(xactor, "role")
        xrole.text = ""
        root.append(xactor)
    nfo_file.write(etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))


if __name__ == "__main__":
    start_time = datetime.datetime.now()
    GetVideoList()
    end_time = datetime.datetime.now()
    print "video detail time:", totaltime_videodetail
    print "all finished time: ", (end_time - start_time).total_seconds()
