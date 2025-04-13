import time
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
from PIL import Image
import io
import os
from bs4 import BeautifulSoup
from urllib.parse import unquote  # Додано для декодування URL

# Налаштування Firefox для x64
service = Service(executable_path="F:\\PythonProject2\\geckodriver.exe")
options = Options()
# options.add_argument("--headless")
driver = webdriver.Firefox(service=service, options=options)
driver.set_window_size(1920, 1080)
print("Firefox запущено")

try:
    url = "https://www.google.com/search?q=default+Images+high+resolution&tbm=isch"
    driver.get(url)
    print(f"Завантаження сторінки: {url}")
    WebDriverWait(driver, 15).until(
        lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "img.YQ4gaf")) > 0
    )
except TimeoutException:
    print("Тайм-аут: сторінка не завантажилась або немає прев’ю.")
    print("Знайдено прев’ю перед тайм-аутом:", len(driver.find_elements(By.CSS_SELECTOR, "img.YQ4gaf")))
    print("Частина HTML для дебагу:", driver.page_source[:10000])
    driver.quit()
    exit()
except Exception as e:
    print(f"Помилка завантаження сторінки: {e}")
    driver.quit()
    exit()

# Прокрутка сторінки
for _ in range(10):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)
print("Сторінка прокручена")

# Знаходимо прев’ю-зображення через Selenium
try:
    thumbnails = driver.find_elements(By.CSS_SELECTOR, "img.YQ4gaf")
    print(f"Знайдено {len(thumbnails)} прев’ю-зображень")
except Exception as e:
    print(f"Помилка пошуку прев’ю: {e}")
    print("Частина HTML для дебагу:", driver.page_source[:10000])
    thumbnails = []

# Створюємо папку
os.makedirs("practice_images/elphie", exist_ok=True)

# Унікальні повнорозмірні зображення із завантаженням у реальному часі
unique_urls = set()
count = 0
MIN_WIDTH, MIN_HEIGHT = 800, 600
for i, thumb in enumerate(thumbnails[:50], 1):
    print(f"Обробка прев’ю {i}...")
    try:
        driver.execute_script("arguments[0].click();", thumb)
        time.sleep(2)

        # Парсимо HTML для отримання <a href="...">
        soup = BeautifulSoup(driver.page_source, "html.parser")
        link = soup.select_one("a[href*='imgres']")
        if link and "imgurl=" in link['href']:
            encoded_src = link['href'].split("imgurl=")[1].split("&")[0]
            src = unquote(encoded_src)  # Декодуємо URL
            print(f"Декодований URL: {src[:50]}...")
            if src and src.startswith("http") and src not in unique_urls:
                try:
                    response = requests.get(src, timeout=5)
                    img = Image.open(io.BytesIO(response.content))
                    width, height = img.size

                    if width >= MIN_WIDTH and height >= MIN_HEIGHT:
                        unique_urls.add(src)
                        count += 1
                        filename = f"practice_images/elphie/image_{count}.jpg"
                        with open(filename, "wb") as f:
                            f.write(response.content)
                        print(
                            f"Зображення додано та завантажено: {src[:50]}... ({width}x{height}, {len(response.content)} байтів)")
                    else:
                        print(f"Зображення пропущено (мала роздільна здатність): {src[:50]}... ({width}x{height})")
                except Exception as e:
                    print(f"Помилка завантаження зображення {i}: {e}")
        else:
            print(f"Помилка обробки прев’ю {i}: Не знайдено посилання imgres")
            print("Частина HTML після кліку:", driver.page_source[:10000])
            links = soup.select("a[href]")
            print(f"Знайдено {len(links)} посилань <a>:")
            for j, l in enumerate(links[:5], 1):
                href = l.get('href')
                print(f"Посилання {j}: {href[:100] if href else 'Без href'}...")
        time.sleep(1)
    except Exception as e:
        print(f"Помилка обробки прев’ю {i}: {e}")
    if count >= 10:
        break

print(f"Завантажено {count} унікальних зображень")
driver.quit()
print("Готово! Перевірте папку practice_images/train")