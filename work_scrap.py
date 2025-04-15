import requests
from bs4 import BeautifulSoup
import csv
import logging
import re
import time
import unicodedata
import random
import os
import gzip
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Налаштування логування
logging.basicConfig(filename="workua_scraper.log", level=logging.INFO)

# Конфігурація дебагінгу
DEBUG_MODE = False  # Увімкнути для збереження всіх HTML-файлів


def create_vacancy_pattern(search_vacancy):
    """
    Створює регулярний вираз для пошуку вакансій за введеним запитом.

    Args:
        search_vacancy (str): Назва вакансії для пошуку (наприклад, "Водій").

    Returns:
        str: Регулярний вираз для відповідності назви вакансії.
    """
    vacancy_base = search_vacancy.lower().strip()
    vacancy_base = re.escape(vacancy_base)
    vacancy_base = unicodedata.normalize("NFKD", vacancy_base).replace("і", "i").replace("ї", "i")
    vacancy_pattern = rf'\b(?:{vacancy_base}(?:[-\s][а-яіїєґ]+)*(?:[,.\s]*(?:кат\.?|категорії?)\s*[A-ZА-ЯІЇЄҐ]+(?:[,\s]*[A-ZА-ЯІЇЄҐ]+)*)?(?:[,.\s\(][а-яіїєґ\s\(\)]+)?)\b'
    return vacancy_pattern


def convert_iso_to_text(iso_date):
    """
    Перетворює дату у форматі ISO (YYYY-MM-DD HH:MM:SS) у текстовий формат (DD місяць YYYY).

    Args:
        iso_date (str): Дата у форматі ISO (наприклад, "2025-04-15 12:00:00").

    Returns:
        str: Дата у текстовому форматі (наприклад, "15 квітня 2025") або оригінальна дата, якщо формат неправильний.
    """
    try:
        date_obj = datetime.strptime(iso_date, "%Y-%m-%d %H:%M:%S")
        months = ["січня", "лютого", "березня", "квітня", "травня", "червня",
                  "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
        return f"{date_obj.day} {months[date_obj.month - 1]} {date_obj.year}"
    except ValueError:
        return iso_date


# Налаштування Selenium для Firefox
firefox_options = Options()
# firefox_options.add_argument("--headless")  # Вимкнено для тестування
firefox_options.add_argument("--no-sandbox")
firefox_options.add_argument("--disable-dev-shm-usage")

# Імітація поведінки браузера
firefox_options.set_preference("general.useragent.override",
                               "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0")

service = Service()
driver = webdriver.Firefox(service=service, options=firefox_options)

# Введення запиту
search_vacancy = input("🔍 Введіть назву вакансії: ").strip().lower()
search_city = input("🌆 Введіть місто: ").strip().lower()
page_input = input("📄 Введіть кількість сторінок для обробки (або 'всі'): ").strip().lower()

# Валідація введення
if not search_vacancy or not search_city:
    print("❌ Помилка: вакансія та місто не можуть бути порожніми!")
    driver.quit()
    exit(1)

# Формуємо базовий URL
search_query = "-".join(search_vacancy.split())
search_city_query = "-".join(search_city.split())
base_url = f"https://www.work.ua/jobs-{search_city_query}-{search_query}/"

# Визначаємо кількість сторінок
if page_input == "всі":
    driver.get(base_url)
    # Явне очікування пагінації
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "pagination"))
        )
    except Exception as e:
        logging.warning(f"Не вдалося знайти пагінацію: {str(e)}")

    soup = BeautifulSoup(driver.page_source, "html.parser")
    pagination = soup.find("ul", class_="pagination")
    max_pages = 1
    if pagination:
        try:
            page_links = pagination.find_all("li")
            for li in page_links[::-1]:
                a_tag = li.find("a")
                if a_tag and "page" in a_tag.get("href", ""):
                    max_pages = int(a_tag["href"].split("page=")[-1])
                    break
            logging.info(f"Знайдено {max_pages} сторінок для обробки")
        except (IndexError, ValueError):
            logging.warning("Не вдалося визначити кількість сторінок, використовуємо 1 сторінку")
    else:
        logging.warning("Пагінація не знайдена, обробляємо лише 1 сторінку")
else:
    try:
        max_pages = int(page_input)
        if max_pages < 1:
            print("❌ Помилка: кількість сторінок має бути більше 0!")
            driver.quit()
            exit(1)
    except ValueError:
        print("❌ Помилка: введіть число або 'всі'!")
        driver.quit()
        exit(1)

logging.info(f"Початок парсингу: вакансія={search_vacancy}, місто={search_city}, сторінок={max_pages}")

jobs = []

page = 1
while page <= max_pages:
    if page == 1:
        driver.get(base_url)
    else:
        # Імітуємо клік по кнопці "Наступна"
        try:
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(@class, 'link-icon') and .//span[text()='Наступна']]"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            current_url = driver.current_url
            next_button.click()
            WebDriverWait(driver, 10).until(
                lambda d: d.current_url != current_url
            )
        except Exception as e:
            logging.error(f"Не вдалося перейти на сторінку {page}: {str(e)}")
            # Зберігаємо HTML для аналізу помилки
            with gzip.open(f"page_{page}_error.html.gz", "wt", encoding="utf-8") as f:
                f.write(driver.page_source)
            logging.info(f"HTML сторінки {page} збережено через помилку в page_{page}_error.html.gz")
            break

    # Явне очікування контейнера PJAX
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "pjax"))
        )
    except Exception as e:
        logging.warning(f"Контейнер PJAX на сторінці {page} не знайдений: {str(e)}")
        # Зберігаємо HTML для аналізу помилки
        with gzip.open(f"page_{page}_error.html.gz", "wt", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.info(f"HTML сторінки {page} збережено через помилку в page_{page}_error.html.gz")

    # Явне очікування вакансій
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "job-link"))
        )
    except Exception as e:
        logging.warning(f"Вакансії на сторінці {page} не знайдені: {str(e)}")
        # Зберігаємо HTML для аналізу помилки
        with gzip.open(f"page_{page}_error.html.gz", "wt", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.info(f"HTML сторінки {page} збережено через помилку в page_{page}_error.html.gz")
        break

    # Імітуємо прокручування сторінки
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(random.uniform(1, 3))

    soup = BeautifulSoup(driver.page_source, "html.parser")
    job_listing = soup.find_all("div", class_="job-link")
    if not job_listing:
        print(f"❌ Вакансій на сторінці {page} не знайдено, зупиняємось.")
        logging.info(f"Вакансій на сторінці {page} не знайдено")
        # Зберігаємо HTML для аналізу помилки
        with gzip.open(f"page_{page}_error.html.gz", "wt", encoding="utf-8") as f:
            f.write(soup.prettify())
        logging.info(f"HTML сторінки {page} збережено через помилку в page_{page}_error.html.gz")
        no_results = soup.find(string=re.compile("Немає результатів|Вакансії не знайдені"))
        if no_results:
            logging.info(f"Сторінка {page} містить повідомлення: {no_results}")
        break
    else:
        logging.info(f"Знайдено {len(job_listing)} вакансій на сторінці {page}")
        if DEBUG_MODE:
            # Зберігаємо HTML лише за умови DEBUG_MODE
            with gzip.open(f"page_{page}.html.gz", "wt", encoding="utf-8") as f:
                f.write(soup.prettify())
            logging.info(f"HTML сторінки {page} збережено в page_{page}.html.gz")
            # Видаляємо старі файли (старше 5 сторінок)
            old_page = page - 5
            if old_page > 0 and os.path.exists(f"page_{old_page}.html.gz"):
                os.remove(f"page_{old_page}.html.gz")
                logging.info(f"Видалено старий файл page_{old_page}.html.gz")

    for job in job_listing:
        try:
            title_tag = job.find("h2")
            title = title_tag.text.strip() if title_tag else "Не знайдено"
            logging.info(f"Обробка вакансії: {title}")

            company = "Невідомо"
            company_div = job.find("div", class_="mt-xs")
            if company_div:
                company_tag = company_div.find("span", class_="strong-600")
                if company_tag:
                    company = company_tag.text.strip()
                    logging.info(f"Знайдено компанію: {company}")
                else:
                    logging.warning(f"Тег компанії не знайдено в div.mt-xs для вакансії {title}")

            salary = "Не вказано"
            salary_tag = job.find("span", class_="strong-600", string=re.compile(r"\d+[  ]?\–[  ]?\d+|\d+"))
            if salary_tag:
                salary = salary_tag.text.strip().replace(" ", "").replace(" ", "").replace("грн", "").replace(" ", "")
                logging.info(f"Знайдено зарплату: {salary}")
            else:
                logging.warning(f"Зарплата не знайдена для вакансії {title}")

            # Спроба знайти місто кількома методами через непередбачувану структуру сайту
            # Метод 1: Пошук <span> без класу, який може містити місто
            city = "Не вказано"
            city_span = job.find("span", class_="")
            if city_span:
                city = city_span.text.strip().rstrip(",").strip()
                logging.info(f"Знайдено місто (метод 1): {city}")
            # Метод 2: Пошук <span> із класом "location"
            if city == "Не вказано":
                city_tag_alt = job.find("span", class_="location")
                if city_tag_alt:
                    city = city_tag_alt.text.strip()
                    logging.info(f"Знайдено місто (метод 2): {city}")
            # Метод 3: Аналіз <div class="mt-xs"> для пошуку тексту, схожого на місто
            if city == "Не вказано":
                city_block = job.find("div", class_="mt-xs")
                if city_block:
                    found_company = False
                    for element in city_block.find_all(["span", "p"]):
                        text = element.text.strip()
                        if not found_company and element.find_parent("span", class_="mr-xs"):
                            found_company = True
                            continue
                        match = re.match(r"^[А-ЯІЇЄҐ][а-яіїєґ\s,-]+", text)
                        if match:
                            city_text = match.group(0).rstrip(",").strip()
                            if not re.search(r"[()№\d]", city_text) and not text.startswith(company.split()[0]):
                                city = city_text.split(",")[0].strip()
                                logging.info(f"Знайдено місто (метод 3): {city}")
                                break
            # Метод 4: Використовуємо CSS-селектор для резервного пошуку міста
            if city == "Не вказано":
                try:
                    city_span_new = job.select_one("div.mt-xs span:nth-child(3)")
                    if city_span_new:
                        city_text = city_span_new.text.strip().rstrip(",").strip()
                        if re.match(r"^[А-ЯІЇЄҐ][а-яіїєґ\s,-]+$", city_text):
                            city = city_text.split(",")[0].strip()
                            logging.info(f"Знайдено місто (метод 4): {city}")
                except Exception as e:
                    logging.warning(f"Метод 4 не спрацював для вакансії {title}: {str(e)}")
            if city == "Не вказано":
                logging.warning(f"Місто не знайдено для вакансії {title}. HTML блоку: {job.prettify()}")

            published_time = "Не вказано"
            title_link = job.find("h2").find("a") if job.find("h2") else None
            if title_link and "title" in title_link.attrs:
                title_text = title_link["title"]
                match = re.search(r"вакансія від (\d{1,2} [а-я]+ \d{4})", title_text)
                if match:
                    published_time = match.group(1)
                    logging.info(f"Знайдено час публікації з атрибуту title для вакансії {title}: {published_time}")
            if published_time == "Не вказано":
                time_tag = job.find("time")
                if time_tag:
                    if "datetime" in time_tag.attrs:
                        published_time = convert_iso_to_text(time_tag["datetime"])
                        logging.info(f"Знайдено час публікації для вакансії {title}: {published_time}")
                    else:
                        published_time = time_tag.text.strip()
                        logging.info(
                            f"Знайдено час публікації (текстовий формат) для вакансії {title}: {published_time}")
            if published_time == "Не вказано":
                logging.warning(f"Час публікації не знайдено для вакансії {title}. HTML блоку: {job.prettify()}")

            link_tag = job.find("h2").find("a") if job.find("h2") else None
            link = "https://www.work.ua" + link_tag["href"] if link_tag else "Посилання не знайдено"

            normalized_title = unicodedata.normalize("NFKD", title.lower()).replace("і", "i").replace("ї", "i")
            vacancy_pattern = create_vacancy_pattern(search_vacancy)
            if re.search(vacancy_pattern, normalized_title, re.IGNORECASE):
                logging.info(f"Вакансія {title} відповідає шаблону")
                if city == "Не вказано" or search_city in city.lower():
                    jobs.append([title, company, salary, city, published_time, link])
                    print(
                        f"Перевірка вакансії: {title} | Компанія: {company} | Зарплата: {salary} | Місто: {city} | Час публікації: {published_time}")
                else:
                    logging.info(
                        f"Вакансія {title} відфільтрована через невідповідність міста: {city} (очікується {search_city})")
            else:
                logging.warning(f"Назва вакансії {title} не відповідає шаблону")

        except Exception as e:
            logging.error(f"Помилка при обробці вакансії {title}: {str(e)}")

    print(f"✅ Сторінка {page} оброблена!")
    logging.info(f"Сторінка {page} оброблена")
    page += 1
    time.sleep(random.uniform(1, 3))

# Закриваємо браузер
driver.quit()


def parse_salary(salary):
    """
    Перетворює текстове значення зарплати у числове для сортування.

    Args:
        salary (str): Зарплата у текстовому форматі (наприклад, "20000", "30000–40000" або "Не вказано").

    Returns:
        float: Середнє значення зарплати для сортування (або 0, якщо зарплата не вказана).
    """
    if salary == "Не вказано":
        return 0
    try:
        if "–" in salary:
            low, high = map(int, salary.split("–"))
            return (low + high) / 2
        return int(salary)
    except ValueError:
        return 0


jobs.sort(key=lambda x: parse_salary(x[2]), reverse=True)

# Збереження у CSV
if jobs:
    with open("workua_jobs.csv", "w", newline="", encoding="UTF-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Назва вакансії", "Компанія", "Зарплата", "Місто", "Час публікації", "Посилання"])
        writer.writerows(jobs)
    print("✅ Вакансії збережено в workua_jobs.csv")
    logging.info("Вакансії збережено в workua_jobs.csv")
else:
    print("❌ Не знайдено жодної вакансії для збереження.")
    logging.warning("Не знайдено жодної вакансії")
