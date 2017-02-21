from bs4 import BeautifulSoup
import smtplib
import requests
from collections import OrderedDict
import sqlite3
import ConfigParser
from email import message

url = "http://www.kijiji.ca"
city = "Toronto+%28GTA%29"
db = "auto"
searchTerm = "car"
locationId = "1700272"  # Needs this one, city seems irrelevant
minprice = ""
maxprice = ""


def fetchPage():
    payload = OrderedDict([
        ('formSubmit', 'true'),
        ('ll', ''),
        ('categoryId', '0'),
        ('categoryName', ''),
        ('locationId', locationId),
        ('pageNumber', '1'),
        ('minPrice', minprice),
        ('maxPrice', maxprice),
        ('adIdRemoved', ''),
        ('sortByName', 'dateDesc'),
        ('userId', ''),
        ('origin', ''),
        ('searchView', 'LIST'),
        ('urgentOnly', 'false'),
        ('cpoOnly', 'false'),
        ('carproofOnly', 'false'),
        ('highlightOnly', 'false'),
        ('gpTopAd', 'false'),
        ('adPriceType', ''),
        ('brand', ''),
        ('keywords', searchTerm),
        ('SearchCategory', '0'),
        ('SearchLocationPicker', city),
        ('SearchSubmit', 'HTTP/1.1')
    ])
    res = requests.get(url + "/b-search.html" + dictToStr(payload), data='')
    if res.ok:
        return res.content
    return "ERR"


def dictToStr(payload):
    payload_string = "?"
    for key, value in payload.items():
        payload_string += str(key + "=" + value + "&")
    payload_string = payload_string[:-1]
    # print payload_string
    return payload_string


def soupifyRawResult(searchResult):
    return BeautifulSoup(searchResult, "lxml")
    # infoDiv = soup.find_all("div", class_="info")
    # print infoDiv[0]


def initConfig():
    global mail_user
    global mail_password
    global db_location
    global mail_receiver

    config = ConfigParser.ConfigParser()
    config.read("/home/d/Documents/PythonProjects/KijijiScraper/app.conf")
    db_location = config.get("DB_Settings", "db_location")
    mail_user = config.get("Mail_Settings", "username")
    mail_password = config.get("Mail_Settings", "password")
    mail_receiver = config.get("Mail_Settings", "receiver")


def initDB():
    global conn
    global c

    sql_query = """CREATE TABLE if not exists {0}
        (id INTEGER PRIMARY KEY, post_title text,post_desc text,
        post_address text, post_price text, post_date text,
        post_url text)""".format(db)
    conn = sqlite3.connect(db_location)
    conn.text_factory = lambda x: unicode(x, "utf-8", "ignore")
    c = conn.cursor()
    c.execute(sql_query)
    conn.commit()


def insertToDB(postList):
    counter = 0
    postList_clone = postList[:]
    print "List size: " + str(len(postList))
    for post in postList_clone:
        # print "Working with " + str(post)
        c = conn.cursor()
        c.execute(
            "SELECT * from " + db + " where post_url=?", (post[5],))
        if(c.fetchone()):
            # print "Skipping {0} Already exists".format(post[5])
            postList.remove(post)
            # print "List length is now " + str(len(postList))
        else:
            c.execute("""insert INTO """ + db + """ (post_title, post_desc, post_address,
            post_price, post_date, post_url)
            VALUES (?,?,?,?,?,?);""", (post[0], post[1], post[2], post[3],
                                       post[4], post[5]))
            counter = counter + 1
    # conn.commit()
    print "List size is now: " + str(len(postList))
    print "Done! Inserted {0} entries".format(counter)
    return postList


def extractUsefulData(data):
    post_title = ""
    post_price = ""
    post_description = ""
    post_date = ""
    post_url = ""
    post_address = ""
    postList = []
    postList_raw = data.find_all("div", class_="info")
    # print postList_raw[1]
    for post in postList_raw:
        post_title_soup = BeautifulSoup(
            str(post.find("div", class_="title")), "lxml")
        post_title_result = post_title_soup.find("a", href=True)
        post_title = post_title_result.contents[
            0].strip().encode("ascii", "ignore")
        post_url = post_title_result['href'].encode("utf-8").strip()
        post_description = post.find("div", class_="description").contents[
            0].encode("utf-8").strip()[:75]
        post_address = post.find("div", class_="location").contents[
            0].encode("utf-8").strip()
        # post_date = BeautifulSoup(str(post.find("div",
        # class_="location")),"lxml").span#.find("span", class_="date-posted")
        post_price = post.find("div", class_="price").contents[
            0].encode("utf-8").strip()
        # postList.append([post_date])
        if ("topAdSearch" not in post_url):  # Don't show ads
            postList.append([post_title, post_description, post_address,
                             post_price, post_date, post_url])
    return postList


def formEmail(postList):
    body = ""
    msg = message.Message()

    for post in postList:
        body += """
            Title: {0}
            Price: {1}
            Description: {2}
            Address: {3}
            Link: www.kijiji.ca{4}

            """.format(post[0], post[3], post[1], post[2], post[5])

    subject = "Kijiji Scraper: {0} Matching Posting(s) for {1}".format(
        str(len(postList)), searchTerm)
    # email_text = """
    #    From: {0}
    #    To: {1}
    #    Subject: {2}
    #
    #    {3}
    #    """.format(mail_user, mail_user, subject, body)
    msg.add_header("from", mail_user)
    msg.add_header("to", mail_receiver)
    msg.add_header("subject", subject)
    msg.set_payload(body)
    return msg.as_string()


def sendEmail(postList):
    email_text = formEmail(postList)

    print "Formed email: "
    print email_text
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.ehlo()
        server.login(mail_user, mail_password)
        server.sendmail(mail_user, mail_user, email_text)
        server.close()
        print "Email sent!"
        return 0
    except Exception as e:
        print "Something went wrong... " + str(e)
        return 1


def main():
    initConfig()
    initDB()
    searchResult = fetchPage()
    soup = soupifyRawResult(searchResult)
    postList = extractUsefulData(soup)
    postList_newEntries = insertToDB(postList)
    if(len(postList_newEntries) > 0):
        if (sendEmail(postList_newEntries) == 0):
            conn.commit()
        else:
            print "Could not send mail, not committing newfound data"
    else:
        print "No new entries!"


if __name__ == "__main__":
    main()
