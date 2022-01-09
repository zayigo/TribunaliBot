import requests
from sqlalchemy.future import select
from database.models import Act, ActInfo, Doc, Court
from logger.logger import log
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
import re
from database.database import SessionFactory

URL_LIST = "https://www.giustizia-amministrativa.it/web/guest/dcsnprr"
QUERY_LENGHT = 100
MAX_PAGES = 10
RE_WHITESPACE = r"\s+|„|“|”|\.{2,}| {2,}"


class Scraper():
    def __init__(self, notification: bool):
        self.notification = notification
        self.acts = []
        self.court = None
        self.req = requests.Session()
        self.last_page = None
        self.url = None
        self.role = "TAR"

    def parse_details(self, act):
        log.info(f"Scraping atto {act}", extra={"tag": self.role})
        dct = {}
        response = self.req.get(act["url_testo"], timeout=60)
        soup = BeautifulSoup(response.text, 'lxml')
        dct["testo"] = soup.get_text("\n", strip=True)
        result_1 = re.search(r"Pubblicato il (\d{2}/\d{2}/\d{4})", response.text)
        if result_1:
            dct["data"] = result_1.group(1)
        result_2 = re.search(r"(\d{2}/\d{2}/\d{4})", response.text)
        if result_2:
            dct["data"] = result_2.group(1)
        p_tags = soup.find_all("p")
        index = 0
        for count, p in enumerate(p_tags):
            if p.has_attr("class") and p["class"][0] == "sezione":
                index = count
                break
        p_text = [p.text for p in soup.find_all("p")[index:]]
        p_text = "\n".join(p_text)
        dct["testo_short"] = re.sub(RE_WHITESPACE, " ", p_text).strip()[:1000]
        return dct

    def parse_list(self, page: int = 0):
        log.info(f"Scraping list {self.court} - page {page}", extra={"tag": self.role})
        reqBody = {
            "_GaSearch_INSTANCE_2NDgCF3zWBwk_hiddenType": "Provvedimenti",
            "_GaSearch_INSTANCE_2NDgCF3zWBwk_pageResultsProvvedimenti": str(QUERY_LENGHT),
            # "_GaSearch_INSTANCE_2NDgCF3zWBwk_DataYearItem": str(datetime.now().year),
            "_GaSearch_INSTANCE_2NDgCF3zWBwk_IsAdvanced": "false",
            "_GaSearch_INSTANCE_2NDgCF3zWBwk_step": str(page),  # pagina 0,1,2
            "_GaSearch_INSTANCE_2NDgCF3zWBwk_sedeProvvedimenti": self.court.raw_name,
        }
        headers = {"Cookie": "LRGASESSION=" + self.req.cookies.get_dict()["LRGASESSION"]}
        response = self.req.post(self.url, verify=False, headers=headers, data=reqBody, timeout=60)
        soup = BeautifulSoup(response.text, 'lxml')
        try:
            self.last_page = int(soup.find_all("li", class_="pagination-number")[-1].text)  # - 1
        except IndexError:
            self.last_page = 0
        acts = soup.find_all("article", class_="ricerca--item")
        self.acts = []
        for a in acts[:-1]:
            parts = a.find_all("div", class_="col-sm-12")
            dct = {"id": parts[-1].b.text.strip()}
            details = parts[1].find_all("b")
            dct["tipo"] = details[0].text.strip()
            dct["sede"] = details[1].text.strip()
            dct["sezione"] = details[2].text.strip()
            dct["numero_provvedimento"] = details[3].text.strip()
            dct["url_testo"] = urllib.parse.urljoin(URL_LIST, parts[0].find("a", href=True)["href"])
            self.acts.append(dct)

    def save_act(self, session, act, send_notification):
        act.uuid_hr = act.uuid_hr.upper().replace(u"\xa0", "").replace(" ", "").strip()
        if Act.get_by_uuid_hr(session, uuid_hr=act.uuid_hr):
            log.debug(f"Duplicate act {act}", extra={"tag": self.role})
            return True
        try:
            session.add(act)
        except Exception:
            log.exception(f"Error while saving act {act}", extra={"tag": self.role})
            session.rollback()
            return False
        session.flush()  # populates id
        act.set_properties()
        act.notify = send_notification
        session.commit()
        log.info(f"New act: {act}", extra={"tag": self.role})
        return False

    def store_act(self, dct, session):
        uuid_hr = f"TAR/{dct['id']}/{dct['numero_provvedimento']}"
        date = datetime.strptime(dct.pop("data"), "%d/%m/%Y")
        act = Act(
            uuid_hr=uuid_hr,
            court_id=self.court.id,
            text=dct.pop("testo_short"),
            full_text=dct.pop("testo"),
            date=date,
            info=ActInfo(docs=[Doc(url=dct.pop("url_testo"), type="web")], extra_info=dct)
        )
        return self.save_act(session, act=act, send_notification=self.notification)

    def scan_court(self):
        # per ottenere il cookie e url corretto
        response = self.req.get(URL_LIST, timeout=60)
        soup = BeautifulSoup(response.text, "lxml")
        formData = soup.find(id="_GaSearch_INSTANCE_2NDgCF3zWBwk_provvedimentiForm")
        self.url = formData["action"]
        self.parse_list()
        self.last_page = min(self.last_page, MAX_PAGES)
        for page in range(self.last_page + 1):
            if page > 0:
                self.parse_list(page)
            if not self.acts:
                log.warn(f"No acts found {self.court.name}", extra={"tag": self.role})
                return
            for dct in self.acts:
                dct = {**dct, **self.parse_details(dct)}
                with SessionFactory() as session:
                    dupe = self.store_act(dct, session)
                    if dupe:
                        break
            if dupe:
                log.info(f"Stopped scanning {self.court.name} - Duplicates found", extra={"tag": self.role})
                break

    def scan(self):
        with SessionFactory() as session:
            courts = session.execute(select(Court)).scalars().all()
        for t in courts:
            log.info(f"Scanning {t}", extra={"tag": self.role})
            self.court = t
            try:
                self.scan_court()
            except:
                log.exception(f"Error while scanning {t}", extra={"tag": self.role})
