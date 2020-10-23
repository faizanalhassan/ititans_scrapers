import logging
import time
import sys
import json
from selenium import webdriver
from selenium.common import exceptions

logging.basicConfig(format='%(levelname)s %(asctime)s:  %(message)s', level=logging.INFO)
from selenium.webdriver.remote.remote_connection import LOGGER
from urllib3.connectionpool import log as urllibLogger

urllibLogger.setLevel(logging.WARNING)
LOGGER.setLevel(logging.WARNING)


class Scraper:
    def __init__(self):
        self.options = webdriver.ChromeOptions()
        self.options.add_argument("--headless")
        self.options.add_argument("--log-level=3")
        self.cd = webdriver.Chrome(options=self.options, service_log_path='NUL')
        self.max_tries = 3
        self.wait_time = 0.5
        self.results = []
        self.tfh = open('temp.jl', 'w')
        self.ofh = open(sys.argv[1], 'w')
        is_driver_quit = False
        try:
            self.start_job()
        except KeyboardInterrupt:
            logging.warning("Keyboard Interrupt. Closing...")
            is_driver_quit = True
        finally:
            logging.info(f"Total Products found: {len(self.results)}.")
            self.tfh.close()
            self.ofh.write(json.dumps(self.results, indent=4))
            self.ofh.close()
            logging.info(f"Output stored to {self.ofh.name}")
            if not is_driver_quit:
                self.cd.quit()

    def start_job(self):
        logging.info("Job started.\nFinding product detail pages...")
        self.cd.get("https://www.onsemi.com/products")
        anchors_without_sub_cat = self.cd.find_elements_by_xpath(
            "//div[not(@data-toggle) and h4]/following-sibling::div//h6[not(./following-sibling::div)]/a")
        sub_cat_anchors = self.cd.find_elements_by_xpath(
            "//div[not(@data-toggle) and h4]/following-sibling::div//h6/following-sibling::div/a")

        detail_pages_urls = [e.get_attribute('href') for e in anchors_without_sub_cat] + \
                            [e.get_attribute('href') for e in sub_cat_anchors]
        logging.info(f'Total product details pages: {len(detail_pages_urls)}.')
        i, j, p_count = 0, 0, 0
        while j < len(detail_pages_urls):
            url = detail_pages_urls[j]
            j += 1
            i += 1
            logging.info(f'Working on page {i}, url = {url}')
            self.cd.get(url)
            self.cd.implicitly_wait(10)
            try:
                self.cd.find_element_by_xpath("//select[@name='pageSize']/option[.='ALL']").click()
            except exceptions.NoSuchElementException:
                new_urls = self.cd.find_elements_by_xpath("//a[.='View Products']")
                if len(new_urls):
                    detail_pages_urls += [e.get_attribute('href') for e in new_urls]
                    logging.info(f"More product details pages URLs found on this page."
                                 f" Total product pages now: {len(detail_pages_urls)}")
                    continue
            time.sleep(2)
            while self.cd.find_elements_by_xpath("//div[@class='px-overlay']//div[@class='spinner-border green']"):
                logging.debug("New data still loading.")
            self.cd.implicitly_wait(0)
            field_names = [self.get_txt_by_xpath('.', e) for e in self.cd.find_elements_by_xpath(
                "//div[contains(@class, 'px-header-cell-heading')]")]

            product_rows = self.cd.find_elements_by_xpath("//div[contains(@class, 'px-row ') and contains(@id, 'r_')]")
            logging.info(f"Products found: {len(product_rows)}")
            for row in product_rows:
                page_data = {}
                for fn in field_names:
                    page_data[fn] = self.get_txt_by_xpath(
                        f"./div[contains(@class, 'px-cell')][{field_names.index(fn) + 1}]"
                        , row)
                    logging.debug(f"{fn} = {page_data[fn]}")
                page_data['verify_url'] = url
                page_data.pop('Select', None)
                page_data.pop("Data Sheet", None)
                self.results.append(page_data)
                self.tfh.write(json.dumps(page_data) + "\n")
                self.tfh.flush()
                p_count += 1
                logging.info(f"Total Products done: {p_count}")

    def click_by_xpath(self, xpath, element=None):
        result = False
        for i in range(self.max_tries):
            result = self.cd.execute_script(f"""
           //console.log(arguments);
            parent = document;
            if(arguments[1]){{
                parent = arguments[1];
            }}
            node = document.evaluate(arguments[0], parent, null,
            XPathResult.FIRST_ORDERED_NODE_TYPE, null ).singleNodeValue;
            //console.log(node);
            if(node){{
             node.scrollIntoView({{
            behavior: 'auto',
            block: 'center',
            inline: 'center'
            }});
             node.click(); 
             return true;
            }}
            return false;
                    """, xpath, element)
            if not result:
                time.sleep(self.wait_time)
            else:
                break
        return result

    def get_txt_by_xpath(self, xpath, element=None):
        value = ''
        for i in range(self.max_tries):
            value = self.cd.execute_script(f"""
           //console.log(arguments);
            parent = document;
            if(arguments[1]){{
                parent = arguments[1];
            }}
            //console.log(parent, 'parent');
            node = document.evaluate(arguments[0], parent, null,
            XPathResult.FIRST_ORDERED_NODE_TYPE, null ).singleNodeValue;
            //console.log(node, arguments);
            if(node){{
             node.scrollIntoView({{
             behavior: 'auto',
             block: 'center',
             inline: 'center'
             }});
             return node.innerText;
            }}
            return '';
            """, xpath, element)
            if value == '':
                time.sleep(self.wait_time)
        # logging.debug(["get_txt_by_xpath", value])
        return value.strip()

    def get_e_by_xpath(self, xpath, element=None):
        e = None
        for i in range(self.max_tries):
            e = self.cd.execute_script(f"""
           //console.log(arguments);
            parent = document;
            if(arguments[1]){{
                parent = arguments[1];
            }}
            //console.log(parent, 'parent');
            node = document.evaluate(arguments[0], parent, null,
            XPathResult.FIRST_ORDERED_NODE_TYPE, null ).singleNodeValue;
            //console.log(node);
            return node != null?node: null;
            """, xpath, element)
            if e is None:
                time.sleep(self.wait_time)
        logging.debug(["get_e_by_xpath", e])
        return e

    def get_attr_by_xpath(self, xpath: str, attr: str, element=None):
        value = ''
        for i in range(self.max_tries):
            value = self.cd.execute_script(f"""
           //console.log(arguments);
            parent = document;
            if(arguments[1]){{
                parent = arguments[1];
            }}
            //console.log(parent, 'parent');
            node = document.evaluate(arguments[0], parent, null,
            XPathResult.FIRST_ORDERED_NODE_TYPE, null ).singleNodeValue;
            //console.log(node);
            if(node){{
             node.scrollIntoView({{
             behavior: 'auto',
             block: 'center',
             inline: 'center'
             }});
             return node.getAttribute(arguments[2]);
            }}
            return '';
            """, xpath, element, attr)
            if value == '':
                time.sleep(self.wait_time)
        logging.debug(["get_attr_by_xpath", value])
        return value.strip()


Scraper()
