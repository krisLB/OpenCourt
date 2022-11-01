import smtplib
from . import sample_config as config
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime as dt

def sendEmail(per, num, total, startTime):
    """Sends out periodic emails during the scraping processs"""
    if num == 0:
        subject = "Volumes Scraped Starting Case Scraper"
        text = "There are " + str(total) + " cases to scrape started at " + str(startTime)
    else:
        subject = 'Your Script is through '+str(per)+ '% ('+str(num)+'/'+str(total)+ ') cases'
        text = "You are now "+str(per)+"% complete with the crawl start was started at "+  str(startTime)
    emailSend(subject, text)

def emailSend(subject, text, smtpserver=config.server):
    """Server Configuration for the sendEmail"""
    html = "<p>"+text+"</p>"
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    frm = config.frm_addr
    to_add = config.to_addr
    message = MIMEMultipart('alternative')
    message['Subject'] = subject
    message['From'] = frm
    message['To'] = ', '.join(to_add)
    message.attach(part1)
    message.attach(part2)
    server = smtplib.SMTP(smtpserver)
    server.starttls()
    server.login(config.user, config.passw)
    problems = server.sendmail(frm, to_add, message.as_string())
    server.quit()


def convertDateFromString(strDate, strInputFormat = '%B %d, %Y'):
    """Convert full representation of date to datetime object"""
    try:
        cDate = dt.datetime.strptime(strDate.trim(), strInputFormat)
    except:
        cDate = strDate
    return cDate
