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
import time
import datetime
from lxml import etree

SERVER = "http://tv.t002.ottcn.com/i-tvbin/qtv_video"
QUA = urllib.quote_plus("QV=1&VN=1.1.27&PT=PVS&RL=1920x1080&IT=12117592000&OS=1.1.27&CHID=13032&DV=tencent_macaroni")
totaltime_videodetail = 0
episode_totalnum = 0


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

    def episode_list(self, cid, index):
        API = '/cover_details/get_cover_videos?tv_cgi_ver=1.0&format=json&req_from=PVS_APK&page_start={0}&page_size=15&video_filter=all&cid={1}&Q-UA={2}'.format(index, cid, QUA)
        return self.get_json(SERVER + API)

    def variety_review(self, column_id, pagesize=15, pagenum=0):
        API = '/column_info/get_column_info?column_id={0}&page_size={1}&page_num={2}&format=json&type=10&Q-UA={3}'.format(column_id, pagesize, pagenum, QUA)
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
        channel_name = channel['chi_name']
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
                try:
                    print title
                except Exception:
                    print "can't print title"
                print channel_id
                if title == "":
                    print "No name exit"
                    return
                if channel_id == "movie":
                    threads.append(gevent.spawn(SaveMovieFiles, cid, item['chi_name'], channel_name))
                elif channel_id in ["tv", "children"]:
                    threads.append(gevent.spawn(SaveTVShowFiles, cid, item['chi_name'], channel_name))
                elif channel_id == "variety":
                    threads.append(gevent.spawn(SaveVarietyFiles, cid, item['chi_name'], channel_name))
    gevent.joinall(threads)


def GetVideoDetail(cid):
    t0 = datetime.datetime.now()
    data = TencentVideo().video_detail(cid)
    t1 = datetime.datetime.now()
    global totaltime_videodetail
    totaltime_videodetail += (t1 - t0).total_seconds()
    return data


def GetEpisodeList(cid, index):
    data = TencentVideo().episode_list(cid, index)
    if "data" in data:
        data = data['data']
        total_num = data.get("video_num", 0)
        global episode_totalnum
        episode_totalnum = total_num
        return data.get("videos")
    else:
        return None


def GetVarietyReview(column_id, index):
    data = TencentVideo().variety_review(column_id, pagenum=index)
    if "data" in data:
        data = data['data']
        return data.get("list")
    else:
        return None


def SaveMovieFiles(cid, filter_name, channel_name):
    data = GetVideoDetail(cid)
    data = data.get("data")
    if not data:
        return
    title = data.get("title").replace(":", "_").replace("?", " ")
    if title == "":
        return
    file_path = "C:\\xbmc-workspace\\LocalDB\\Movies\\"
    strm_path = file_path + title + ".strm"
    nfo_path = file_path + title + ".nfo"
    with open(strm_path, "w+") as f1:
        f1.write("playvideo")
    if not NeedAddNfoFile(nfo_path, filter_name):
        return
    with open(nfo_path, "w+") as f2:
        CreateMovieNfoFiles(data, filter_name, channel_name, f2)


def SaveTVShowFiles(cid, filter_name, channel_name):
    data = GetVideoDetail(cid)
    data = data.get("data")
    if not data:
        return
    title = data.get("title").replace(":", "_")
    if title == "":
        return
    file_path = "C:\\xbmc-workspace\\LocalDB\\TVShows\\" + title
    if not os.path.exists(file_path):
        os.mkdir(file_path)
    nfo_path = file_path + "\\tvshow.nfo"
    if not NeedAddNfoFile(nfo_path, filter_name):
        return
    with open(nfo_path, "w+") as f:
        CreateTVShowNfoFiles(data, filter_name, channel_name, f)
    SaveSeasonEpisodeFiles(data.get("c_id"), title, filter_name, channel_name, file_path)


def SaveSeasonEpisodeFiles(cid, tv_title, filter_name, channel_name, file_path, page=0):
    if not cid:
        return
    episode_list = GetEpisodeList(cid, page)
    if not episode_list:
        return
    count = 1
    for episode in episode_list:
        epi_title = episode['v_title']
        strm_path = set_episode_strm_path(file_path, tv_title, epi_title, channel_name, count)
        nfo_path = strm_path[:-5] + ".nfo"
        if not NeedAddNfoFile(nfo_path, filter_name):
            return
        with open(strm_path, "w+") as f1, open(nfo_path, "w+") as f2:
            f1.write(episode['play_url'])
            CreateEpisodeNfoFiles(episode, count, tv_title, channel_name, filter_name, f2)
        count += 1


def SaveVarietyFiles(cid, filter_name, channel_name):
    data = GetVideoDetail(cid)
    data = data.get("data")
    if not data:
        return
    title = data.get("title").replace(":", "_")
    if title == "":
        return
    file_path = "C:\\xbmc-workspace\\LocalDB\\TVShows\\" + title
    if not os.path.exists(file_path):
        os.mkdir(file_path)
    nfo_path = file_path + "\\tvshow.nfo"
    if not NeedAddNfoFile(nfo_path, filter_name):
        return
    with open(nfo_path, "w+") as f:
        CreateVarietyNfoFiles(data, filter_name, channel_name, f)
    SaveVarietyReviewFiles(data.get("column_id"), title, filter_name, channel_name, file_path)


def SaveVarietyReviewFiles(column_id, var_title, filter_name, channel_name, file_path, page=0):
    if not column_id:
        return
    review_list = GetVarietyReview(column_id, page)
    if not review_list:
        return
    count = 1
    for review in review_list:
        date = review['publish_date'][:10]
        strm_path = file_path + "\\" + var_title + "_" + date + ".strm"
        nfo_path = strm_path[:-5] + ".nfo"
        if not NeedAddNfoFile(nfo_path, filter_name):
            return
        with open(strm_path, "w+") as f1, open(nfo_path, "w+") as f2:
            f1.write("playvideo")
            CreateReviewNfoFiles(review, count, var_title, filter_name, channel_name, f2)
        count += 1


def CreateMovieNfoFiles(movie_item, filter_name, channel_name, nfo_file):
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
    # tag userrating
    xuserrating = etree.Element("userrating")
    xuserrating.text = ""
    root.append(xuserrating)
    # tag year
    xyear = etree.Element("year")
    xyear.text = movie_item.get("year")
    root.append(xyear)
    # tag premiered
    xpremiered = etree.Element("premiered")
    xpremiered.text = movie_item.get("publish_date")
    root.append(xpremiered)
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
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = movie_item['cover_pictures'].get("pic_260x364")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = movie_item['cover_pictures'].get("pic_350x490")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = movie_item.get("ver_pic_url")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = movie_item['cover_pictures'].get("pic_498x280")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = movie_item['cover_pictures'].get("pic_408x230")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = movie_item.get("hori_pic_url")
    root.append(xthumb)
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
    xplaycount.text = ""
    root.append(xplaycount)
    # tag lastplayed
    xlastplayed = etree.Element("lastplayed")
    xlastplayed.text = ""
    root.append(xlastplayed)
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
    xgenre.text = ""
    root.append(xgenre)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = channel_name
    root.append(xtag)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = filter_name
    root.append(xtag)
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
    # tag status
    xstatus = etree.Element("status")
    xstatus.text = ""
    root.append(xstatus)
    # tag code
    xcode = etree.Element("code")
    xcode.text = ""
    root.append(xcode)
    # tag aired
    xaired = etree.Element("aired")
    xaired.text = ""
    root.append(xaired)
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
        xorder = etree.SubElement(xactor, "order")
        xorder.text = ""
        xthumb = etree.SubElement(xactor, "thumb")
        xthumb.text = ""
        root.append(xactor)
    # tag resume
    xresume = etree.Element("resume")
    xposition = etree.SubElement(xresume, "position")
    xposition.text = ""
    xtotal = etree.SubElement(xresume, "total")
    xtotal.text = ""
    root.append(xresume)
    # tag dateadded
    xdateadded = etree.Element("dateadded")
    xdateadded.text = SecondtoYMDHMS(time.time())
    root.append(xdateadded)
    nfo_file.write(etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))


def CreateTVShowNfoFiles(tv_item, filter_name, channel_name, nfo_file):
    title = tv_item.get("title")
    # tvshow *.nfo file
    root = etree.Element("tvshow")
    # tag title
    xtitle = etree.Element("title")
    xtitle.text = title
    root.append(xtitle)
    # tag showtitle
    xshowtitle = etree.Element("showtitle")
    xshowtitle.text = title
    root.append(xshowtitle)
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
    xseason.text = "0"
    root.append(xseason)
    # tag episode
    xepisode = etree.Element("episode")
    xepisode.text = tv_item.get("episode_all")
    root.append(xepisode)
    # tag displayseason
    xdisplayseason = etree.Element("displayseason")
    xdisplayseason.text = "-1"
    root.append(xdisplayseason)
    # tag displayepisode
    xdisplayepisode = etree.Element("displayepisode")
    xdisplayepisode.text = "-1"
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
    xtagline.text = ""
    root.append(xtagline)
    # tag runtime
    xruntime = etree.Element("runtime")
    xruntime.text = ""
    root.append(xruntime)
    # tag thumb
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = tv_item['cover_pictures'].get("pic_770x1080")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = tv_item['cover_pictures'].get("pic_260x364")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = tv_item['cover_pictures'].get("pic_350x490")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = tv_item.get("ver_pic_url")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = tv_item['cover_pictures'].get("pic_498x280")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = tv_item['cover_pictures'].get("pic_408x230")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = tv_item.get("hori_pic_url")
    root.append(xthumb)
    # tag fanart
    xfanart = etree.Element("fanart")
    xthumb = etree.SubElement(xfanart, "thumb")
    xthumb.text = tv_item['cover_pictures'].get("pic_1920x1080")
    root.append(xfanart)
    # tag mpaa
    xmpaa = etree.Element("mpaa")
    xmpaa.text = ""
    root.append(xmpaa)
    # tag playcount
    xplaycount = etree.Element("playcount")
    xplaycount.text = ""
    root.append(xplaycount)
    # tag lastplayed
    xlastplayed = etree.Element("lastplayed")
    xlastplayed.text = ""
    root.append(xlastplayed)
    # tag episodeguide
    xepisodeguide = etree.Element("episodeguide")
    xepisodeguide.text = ""
    root.append(xepisodeguide)
    # tag id
    xid = etree.Element("id")
    xid.text = tv_item.get("c_id")
    root.append(xid)
    # tag uniqueid
    xuniqueid = etree.Element("uniqueid")
    xuniqueid.text = ""
    root.append(xuniqueid)
    # tag filenameandpath
    xpath = etree.Element("filenameandpath")
    xpath.text = ""
    root.append(xpath)
    # tag status
    xstatus = etree.Element("status")
    xstatus.text = ""
    root.append(xstatus)
    # tag code
    xcode = etree.Element("code")
    xcode.text = ""
    root.append(xcode)
    # tag aired
    xaired = etree.Element("aired")
    xaired.text = ""
    root.append(xaired)
    # tag trailer
    xtrailer = etree.Element("trailer")
    root.append(xtrailer)
    # tag genre
    xgenre = etree.Element("genre")
    xgenre.text = ""
    root.append(xgenre)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = channel_name
    root.append(xtag)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = filter_name
    root.append(xtag)
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
    # tag resume
    xresume = etree.Element("resume")
    xposition = etree.SubElement(xresume, "position")
    xposition.text = ""
    xtotal = etree.SubElement(xresume, "total")
    xtotal.text = ""
    root.append(xresume)
    # tag dateadded
    xdateadded = etree.Element("dateadded")
    xdateadded.text = SecondtoYMDHMS(time.time())
    root.append(xdateadded)
    nfo_file.write(etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))


def CreateEpisodeNfoFiles(epi_item, index, tv_title, channel_name, filter_name, nfo_file):
    title = epi_item.get("v_title")
    # episodedetails *.nfo file
    root = etree.Element("episodedetails")
    # tag title
    xtitle = etree.Element("title")
    xtitle.text = title
    root.append(xtitle)
    # tag showtitle
    xshowtitle = etree.Element("showtitle")
    if channel_name == u"少儿":
        showtitle = epi_item.get("v_s_title")
    else:
        showtitle = tv_title
    xshowtitle.text = showtitle
    root.append(xshowtitle)
    # tag rate
    xrate = etree.Element("rate")
    xrate.text = ""
    root.append(xrate)
    # tag userrating
    xuserrating = etree.Element("userrating")
    xuserrating.text = ""
    root.append(xuserrating)
    # tag top250
    xtop250 = etree.Element("top250")
    xtop250.text = ""
    root.append(xtop250)
    # tag season
    xseason = etree.Element("season")
    xseason.text = ""
    root.append(xseason)
    # tag episode
    xepisode = etree.Element("episode")
    xepisode.text = str(index)
    # tag displayseason
    xdisplayseason = etree.Element("displayseason")
    xdisplayseason.text = "-1"
    root.append(xdisplayseason)
    # tag displayepisode
    xdisplayepisode = etree.Element("displayepisode")
    xdisplayepisode.text = "-1"
    root.append(xdisplayepisode)
    # tag outline
    xoutline = etree.Element("outline")
    xoutline.text = epi_item.get("tips")
    root.append(xoutline)
    # tag plot
    xplot = etree.Element("plot")
    xplot.text = epi_item.get("v_description")
    root.append(xplot)
    # tag tagline
    xtagline = etree.Element("tagline")
    xtagline.text = ""
    root.append(xtagline)
    # tag runtime
    xruntime = etree.Element("runtime")
    xruntime.text = str(int(epi_item.get("duration")) / 60)
    root.append(xruntime)
    # tag thumb
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = epi_item['v_ext_info'].get("pic_228x128")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = epi_item['v_ext_info'].get("pic_160x90")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = epi_item['v_ext_info'].get("pic_496x280")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = epi_item['v_ext_info'].get("pic_640x360")
    root.append(xthumb)
    # tag mpaa
    xmpaa = etree.Element("mpaa")
    xmpaa.text = ""
    root.append(xmpaa)
    # tag playcount
    xplaycount = etree.Element("playcount")
    xplaycount.text = ""
    root.append(xplaycount)
    # tag lastplayed
    xlastplayed = etree.Element("lastplayed")
    xlastplayed.text = ""
    root.append(xlastplayed)
    # tag id
    xid = etree.Element("id")
    xid.text = epi_item['v_id']
    root.append(xid)
    # tag uniqueid
    xuniqueid = etree.Element("uniqueid")
    xuniqueid.text = ""
    root.append(xuniqueid)
    # tag genre
    xgenre = etree.Element("genre")
    xgenre.text = ""
    root.append(xgenre)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = channel_name
    root.append(xtag)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = filter_name
    root.append(xtag)
    # tag credits
    xcredits = etree.Element("credits")
    xcredits.text = ""
    root.append(xcredits)
    # tag director
    xdirector = etree.Element("director")
    xdirector.text = ""
    root.append(xdirector)
    # tag premiered
    xpremiered = etree.Element("premiered")
    xpremiered.text = epi_item.get("create_time")[:10]
    root.append(xpremiered)
    # tag year
    xyear = etree.Element("year")
    xyear.text = epi_item.get("create_time")[:4]
    root.append(xyear)
    # tag status
    xstatus = etree.Element("status")
    xstatus.text = ""
    root.append(xstatus)
    # tag code
    xcode = etree.Element("code")
    xcode.text = ""
    root.append(xcode)
    # tag aired
    xaired = etree.Element("aired")
    xaired.text = epi_item['v_ext_info'].get("publish_date")
    root.append(xaired)
    # tag studio
    xstudio = etree.Element("studio")
    xstudio.text = ""
    root.append(xstudio)
    # tag trailer
    xtrailer = etree.Element("trailer")
    xtrailer.text = ""
    root.append(xtrailer)
    # tag actor
    xactor = etree.Element("actor")
    xactor.text = ""
    root.append(xactor)
    # tag resume
    xresume = etree.Element("resume")
    xposition = etree.SubElement(xresume, "position")
    xposition.text = ""
    xtotal = etree.SubElement(xresume, "total")
    xtotal.text = ""
    root.append(xresume)
    # tag dateadded
    xdateadded = etree.Element("dateadded")
    xdateadded.text = SecondtoYMDHMS(time.time())
    root.append(xdateadded)
    nfo_file.write(etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))


def CreateVarietyNfoFiles(variety_item, filter_name, channel_name, nfo_file):
    title = variety_item.get("title")
    # tvshow *.nfo file
    root = etree.Element("tvshow")
    # tag title
    xtitle = etree.Element("title")
    xtitle.text = title
    root.append(xtitle)
    # tag showtitle
    xshowtitle = etree.Element("showtitle")
    xshowtitle.text = title
    root.append(xshowtitle)
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
    xrating.text = variety_item.get("score")
    root.append(xrating)
    # tag year
    xyear = etree.Element("year")
    xyear.text = variety_item.get("year")
    root.append(xyear)
    # tag top250
    xtop250 = etree.Element("top250")
    root.append(xtop250)
    # tag season
    xseason = etree.Element("season")
    xseason.text = "0"
    root.append(xseason)
    # tag episode
    xepisode = etree.Element("episode")
    xepisode.text = variety_item.get("episode_all")
    root.append(xepisode)
    # tag displayseason
    xdisplayseason = etree.Element("displayseason")
    xdisplayseason.text = "-1"
    root.append(xdisplayseason)
    # tag displayepisode
    xdisplayepisode = etree.Element("displayepisode")
    xdisplayepisode.text = "-1"
    root.append(xdisplayepisode)
    # tag votes
    xvotes = etree.Element("votes")
    root.append(xvotes)
    # tag outline
    xoutline = etree.Element("outline")
    xoutline.text = variety_item.get("s_title")
    root.append(xoutline)
    # tag plot
    xplot = etree.Element("plot")
    xplot.text = variety_item.get("c_description")
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
    xthumb.text = variety_item['cover_pictures'].get("pic_770x1080")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = variety_item['cover_pictures'].get("pic_260x364")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = variety_item['cover_pictures'].get("pic_350x490")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = variety_item.get("ver_pic_url")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = variety_item['cover_pictures'].get("pic_498x280")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = variety_item['cover_pictures'].get("pic_408x230")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = variety_item.get("hori_pic_url")
    root.append(xthumb)
    # tag fanart
    xfanart = etree.Element("fanart")
    xthumb = etree.SubElement(xfanart, "thumb")
    xthumb.text = variety_item['cover_pictures'].get("pic_1920x1080")
    root.append(xfanart)
    # tag mpaa
    xmpaa = etree.Element("mpaa")
    xmpaa.text = ""
    root.append(xmpaa)
    # tag playcount
    xplaycount = etree.Element("playcount")
    xplaycount.text = ""
    root.append(xplaycount)
    # tag lastplayed
    xlastplayed = etree.Element("lastplayed")
    xlastplayed.text = ""
    root.append(xlastplayed)
    # tag episodeguide
    xepisodeguide = etree.Element("episodeguide")
    xepisodeguide.text = ""
    root.append(xepisodeguide)
    # tag id
    xid = etree.Element("id")
    xid.text = variety_item.get("c_id")
    root.append(xid)
    # tag uniqueid
    xuniqueid = etree.Element("uniqueid")
    xuniqueid.text = ""
    root.append(xuniqueid)
    # tag filenameandpath
    xpath = etree.Element("filenameandpath")
    xpath.text = ""
    root.append(xpath)
    # tag status
    xstatus = etree.Element("status")
    xstatus.text = ""
    root.append(xstatus)
    # tag code
    xcode = etree.Element("code")
    xcode.text = ""
    root.append(xcode)
    # tag aired
    xaired = etree.Element("aired")
    xaired.text = ""
    root.append(xaired)
    # tag trailer
    xtrailer = etree.Element("trailer")
    root.append(xtrailer)
    # tag genre
    xgenre = etree.Element("genre")
    xgenre.text = ""
    root.append(xgenre)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = channel_name
    root.append(xtag)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = filter_name
    root.append(xtag)
    # tag country
    xcountry = etree.Element("country")
    xcountry.text = variety_item.get("area_name")
    root.append(xcountry)
    # tag premiered
    xpremiered = etree.Element("premiered")
    xpremiered.text = variety_item.get("publish_date")
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
    director_list = variety_item.get("directors")
    for item in director_list:
        xdirector = etree.Element("director")
        xdirector.text = item
        root.append(xdirector)
    # tag actor
    actor_list = variety_item.get("guests")
    for item in actor_list:
        xactor = etree.Element("actor")
        xname = etree.SubElement(xactor, "name")
        xname.text = item
        xrole = etree.SubElement(xactor, "role")
        xrole.text = ""
        root.append(xactor)
    # tag resume
    xresume = etree.Element("resume")
    xposition = etree.SubElement(xresume, "position")
    xposition.text = ""
    xtotal = etree.SubElement(xresume, "total")
    xtotal.text = ""
    root.append(xresume)
    # tag dateadded
    xdateadded = etree.Element("dateadded")
    xdateadded.text = SecondtoYMDHMS(time.time())
    root.append(xdateadded)
    nfo_file.write(etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))


def CreateReviewNfoFiles(rev_item, index, tv_title, channel_name, filter_name, nfo_file):
    title = rev_item.get("title")
    # episodedetails *.nfo file
    root = etree.Element("episodedetails")
    # tag title
    xtitle = etree.Element("title")
    xtitle.text = title
    root.append(xtitle)
    # tag showtitle
    xshowtitle = etree.Element("showtitle")
    xshowtitle.text = tv_title
    root.append(xshowtitle)
    # tag rate
    xrate = etree.Element("rate")
    xrate.text = ""
    root.append(xrate)
    # tag userrating
    xuserrating = etree.Element("userrating")
    xuserrating.text = ""
    root.append(xuserrating)
    # tag top250
    xtop250 = etree.Element("top250")
    xtop250.text = ""
    root.append(xtop250)
    # tag season
    xseason = etree.Element("season")
    xseason.text = ""
    root.append(xseason)
    # tag episode
    xepisode = etree.Element("episode")
    xepisode.text = str(index)
    # tag displayseason
    xdisplayseason = etree.Element("displayseason")
    xdisplayseason.text = "-1"
    root.append(xdisplayseason)
    # tag displayepisode
    xdisplayepisode = etree.Element("displayepisode")
    xdisplayepisode.text = "-1"
    root.append(xdisplayepisode)
    # tag outline
    xoutline = etree.Element("outline")
    xoutline.text = rev_item.get("second_title")
    root.append(xoutline)
    # tag plot
    xplot = etree.Element("plot")
    xplot.text = rev_item.get("v_description")
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
    xthumb = etree.Element("thumb", aspect="banner")
    xthumb.text = rev_item.get("img_url_2")
    root.append(xthumb)
    xthumb = etree.Element("thumb", aspect="poster")
    xthumb.text = rev_item.get("img_url_1")
    root.append(xthumb)
    # tag mpaa
    xmpaa = etree.Element("mpaa")
    xmpaa.text = ""
    root.append(xmpaa)
    # tag playcount
    xplaycount = etree.Element("playcount")
    xplaycount.text = ""
    root.append(xplaycount)
    # tag lastplayed
    xlastplayed = etree.Element("lastplayed")
    xlastplayed.text = ""
    root.append(xlastplayed)
    # tag id
    xid = etree.Element("id")
    xid.text = rev_item['cover_id']
    root.append(xid)
    # tag uniqueid
    xuniqueid = etree.Element("uniqueid")
    xuniqueid.text = ""
    root.append(xuniqueid)
    # tag genre
    xgenre = etree.Element("genre")
    xgenre.text = ""
    root.append(xgenre)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = channel_name
    root.append(xtag)
    # tag tag
    xtag = etree.Element("tag")
    xtag.text = filter_name
    root.append(xtag)
    # tag credits
    xcredits = etree.Element("credits")
    xcredits.text = ""
    root.append(xcredits)
    # tag director
    xdirector = etree.Element("director")
    xdirector.text = ""
    root.append(xdirector)
    # tag premiered
    xpremiered = etree.Element("premiered")
    xpremiered.text = rev_item.get("publish_date")
    root.append(xpremiered)
    # tag year
    xyear = etree.Element("year")
    xyear.text = rev_item.get("publish_date")[:4]
    root.append(xyear)
    # tag status
    xstatus = etree.Element("status")
    xstatus.text = ""
    root.append(xstatus)
    # tag code
    xcode = etree.Element("code")
    xcode.text = ""
    root.append(xcode)
    # tag aired
    xaired = etree.Element("aired")
    xaired.text = rev_item.get("publish_date")
    root.append(xaired)
    # tag studio
    xstudio = etree.Element("studio")
    xstudio.text = ""
    root.append(xstudio)
    # tag trailer
    xtrailer = etree.Element("trailer")
    xtrailer.text = ""
    root.append(xtrailer)
    # tag actor
    xactor = etree.Element("actor")
    xactor.text = ""
    root.append(xactor)
    # tag resume
    xresume = etree.Element("resume")
    xposition = etree.SubElement(xresume, "position")
    xposition.text = ""
    xtotal = etree.SubElement(xresume, "total")
    xtotal.text = ""
    root.append(xresume)
    # tag dateadded
    xdateadded = etree.Element("dateadded")
    xdateadded.text = SecondtoYMDHMS(time.time())
    root.append(xdateadded)
    nfo_file.write(etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))


def SecondtoYMDHMS(secTime):
    return str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(secTime)))


def NeedAddNfoFile(nfo_path, filter_name):
    if not os.path.exists(nfo_path):
        return True
    else:
        add_xml_node_tag(nfo_path, filter_name)
        return False


def add_xml_node_tag(nfo_path, filter_name):
    is_exit = False
    xml = etree.parse(nfo_path)
    root = xml.getroot()
    node = root.xpath("//tag")
    for item in node:
        if filter_name == item.text:
            is_exit = True
            break
    if not is_exit:
        xtag = etree.Element("tag")
        xtag.text = filter_name
        root.append(xtag)
        with open(nfo_path, "w+") as f:
            f.write(etree.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True))
        print "Add New Tag: " + filter_name


def make_episode_index(num, index):
    head_index = ""
    if num in range(1, 10):
        head_index = "0"
    elif num in range(10, 100):
        if index in range(1, 10):
            head_index = "0"
    elif num in range(100, 1000):
        if index in range(1, 10):
            head_index = "00"
        elif index in range(10, 100):
            head_index = "0"
    else:
        if index in range(1, 10):
            head_index = "000"
        elif index in range(10, 100):
            head_index = "00"
        elif index in range(100, 1000):
            head_index = "0"
    return head_index + str(index)


def set_episode_strm_path(file_path, tv_title, epi_title, channel_name, count):
    strm_path = ""
    file_path = file_path + "\\"
    if channel_name == u"少儿":
        epi_info = tv_title + "_ep" + make_episode_index(episode_totalnum, count)
    else:
        epi_info = epi_title.replace("_", "_ep")
    strm_path = file_path + epi_info + ".strm"
    return strm_path


if __name__ == "__main__":
    start_time = datetime.datetime.now()
    GetVideoList()
    end_time = datetime.datetime.now()
    print "video detail time:", totaltime_videodetail
    print "all finished time: ", (end_time - start_time).total_seconds()
