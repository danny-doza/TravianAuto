# !!! DO NOT MODIFY DIRECTLY, USE .ipynb TO EXPORT AND OVERWRITE WHEN UPDATES ARE MADE

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException, TimeoutException, WebDriverException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

from apscheduler.schedulers.background import BackgroundScheduler

from contextlib import contextmanager

from rich.console import Console
from rich.layout import Layout
from rich.table import Table
from rich.live import Live
from rich import box

from getpass import getpass

from datetime import datetime, timedelta, timezone
import ipywidgets as widgets
from IPython.display import display
import pandas as pd
import re
import random
import requests
import subprocess
import time

console = Console()

REFRESH = 'refresh'
RESOURCE_FIELDS = 'resource_fields'
ADVENTURES = 'adventures'
HERO_UPGRADE = 'hero_upgrade'
GOLD_CLUB_CHECK = 'gold_club_check'
COLLECT_MISSION_RESOURCES = 'collect_mission_resources'
COLLECT_DAILY_QUEST_REWARDS = 'collect_daily_rewards'
TRAIN_TROOPS = 'train_troops'
CHECK_FOR_INCOMING_ATTACKS = 'attack_check'
SPEND_ALL_RESOURCES = 'spend_all'
RAIDS = 'raids'
logs = {}

WOOD = 1
CLAY = 2
IRON = 3
WHEAT = 4
resource_ids = [WOOD, CLAY, IRON, WHEAT]

JS_CLICK = "arguments[0].click();"
JS_SCROLL_INTO_VIEW = "arguments[0].scrollIntoView(true);"

# helper funcs
def calc_new_interval_between(x, y):
    return random.uniform(x, y)


def refresh_page(drivers_info, driver, scheduler=None):
    driver.refresh()

    if scheduler:
        scheduler.add_job(refresh_page, 'interval', seconds=calc_new_interval_between(698, 722),
                          id=f"{drivers_info[driver]['Username']}_{REFRESH}",
                          args=[drivers_info, driver, scheduler], replace_existing=True)

# %%
''' web driver init. '''

def run_command_in_background(command):
    return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)


def run_command_in_background_and_wait_for_output(command, expected_output, timeout=30):
    process = run_command_in_background(command)

    end_time = time.time() + timeout
    while time.time() < end_time:
        output = process.stdout.read(1024).decode('utf-8')

        if expected_output in output:
            print("Expected output received.")
            return True

        time.sleep(1)

    print("Timeout or process ended without producing expected output.")
    return False


def init_webdriver(proxy_port=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--ignore-certificate-errors")

    # Disable image loading
    #prefs = {"profile.managed_default_content_settings.images": 2}
    #options.add_experimental_option("prefs", prefs)

    if proxy_port:
        proxy_address = f'localhost:{proxy_port}'
        options.add_argument(f'--proxy-server=http://{proxy_address};https://{proxy_address}')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get('https://httpbin.org/ip')
        return driver
    except WebDriverException:
        run_command_in_background_and_wait_for_output('proxy-manager', 'Proxy Manager is running')
        
        try:
            driver.refresh()         
            return driver
        except WebDriverException:
            return None
        
# Context manager for Selenium Web Driver
@contextmanager
def managed_webdriver(proxy_port=None):
    driver = init_webdriver(proxy_port)
    try:
        yield driver
    finally:
        print("Shutting down web driver...")
        driver.quit()

# %%
''' scheduler init. '''

def cleanup_scheduler(scheduler):
    if scheduler.running:
        print("Shutting down scheduler...")
        scheduler.shutdown(wait=True)
    else:
        print("Scheduler already stopped.")

# Context manager for BackgroundScheduler
@contextmanager
def managed_scheduler(*args, **kwargs):
    scheduler = BackgroundScheduler(*args, **kwargs)
    scheduler.start()
    try:
        yield scheduler
    finally:
        cleanup_scheduler(scheduler)

# %%
''' contextual help (dialog) helpers'''

def disable_contextual_help(driver):
    button_options = driver.find_element(By.XPATH, '//a[contains(@href, "/options")]')
    driver.execute_script(JS_CLICK, button_options) # use js to get around helper popup

    checkbox_contextual_help = driver.find_element(By.XPATH, '//*[@id="hideContextualHelp"]')
    checkbox_contextual_help.click()
    
    save_button = driver.find_element(By.CSS_SELECTOR, '.textButtonV1.green')
    driver.execute_script(JS_SCROLL_INTO_VIEW, save_button)
    save_button.click()


def dismiss_report_helper_popup(driver):
    button_reports = driver.find_element(By.XPATH, '//*[@id="navigation"]/a[5]')
    driver.execute_script(JS_CLICK, button_reports) # use js to get around helper popup


def dismiss_ok_popup(driver):
    try:
        button_ok = driver.find_element(By.XPATH, '//*[@id="contextualHelp"]/div/div[2]/nav/button')
        driver.execute_script(JS_CLICK, button_ok) # use js to get around helper popup
    except NoSuchElementException:
        pass


def dismiss_deal(driver):
    try:
        #TODO: FINISH TESTING THIS
        button_dismiss = driver.find_element(By.XPATH, '//*[starts-with(@id, "oneTimeOfferAnnouncement")]')
        button_dismiss.click()
    except NoSuchElementException:
        pass


# %%
''' Open Travian International 2 server and login if not already '''

def attempt_login(site, username, password, driver, retry=True):
    driver.get(site)

    try:
        input_username = driver.find_element(By.XPATH, '//*[@id="loginForm"]/tbody/tr[1]/td[2]/input')
        input_pwd = driver.find_element(By.XPATH, '//*[@id="loginForm"]/tbody/tr[2]/td[2]/input')
        button_login = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"][value="Login"].textButtonV1.green')

        input_username.send_keys(username)
        input_pwd.send_keys(password)
        button_login.click()

        #driver.refresh()
    except NoSuchElementException:
        driver.refresh()

        if retry:
            attempt_login(site, username, password, driver)
    
    dismiss_deal(driver) # TODO: TESTING NOW

# %%
''' navigation helpers '''

def navigate_to_page(driver, page_css_selector, url_check):
    if not url_check or url_check not in driver.current_url:
        try:
            button_hero_overview = WebDriverWait(driver, 7).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, page_css_selector))
            )
        except TimeoutException:
            driver.refresh()
            button_hero_overview = WebDriverWait(driver, 7).until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, page_css_selector))
            )
        
        if button_hero_overview:
            try:
                button_hero_overview.click()
            except ElementClickInterceptedException:
                driver.execute_script(JS_CLICK, button_hero_overview)       


def navigate_to_hero_inventory(driver):
    selector = '#heroImageButton'
    url_check = 'hero/inventory'
    navigate_to_page(driver, selector, url_check)


def navigate_to_resource_fields(driver):
    selector = '.village.resourceView'
    url_check = 'dorf1.php'
    navigate_to_page(driver, selector, url_check)


def navigate_to_buildings(driver):
    selector = '.village.buildingView'
    url_check = 'dorf2.php'
    navigate_to_page(driver, selector, url_check)


def enter_building(driver, building):
    navigate_to_buildings(driver)

    selector = f'[data-name="{building}"]'
    url_check = None
    navigate_to_page(driver, selector, url_check)

# %%
''' building construction funcs '''

def can_build(building_slot):
    if 'good' not in building_slot.get_attribute('class'):
        print("Unable to upgrade, please ensure you have enough resources and building queue is not full.")
        return False
    return True


def press_construct_building_button_for(driver, building):
    try:
        header = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
            (By.XPATH, f"//h2[text()='{building}']"))
        )
    except TimeoutException:
        print("Unable to find building! Has it already been constructed or are you on the wrong building tab?")
        return False

    building_wrapper = header.find_element(By.XPATH, '..')
    build_button = building_wrapper.find_element(By.CSS_SELECTOR, '.textButtonV1.green.new')
    build_button.click()

    return True

def construct_building_in_slot(driver, building, building_slot):
    navigate_to_buildings(driver)

    building_slot = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.XPATH, f"//a[contains(@href, '/build.php?id={building_slot}')]"))
    )
    if not can_build(building_slot):
        return

    driver.execute_script(JS_CLICK, building_slot) # use javascript to get around helper popup

    for i in range(1, 4): # check all building tabs for building
        try:
            infrastructure_tab = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
                (By.XPATH, f"//a[contains(@href, '/build.php?id={building_slot}&category={i}')]"))
            )

            infrastructure_tab.click()
        except TimeoutException: # if tab not found we have another helper popup, dismiss it then retry
            popup_next_button = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
                (By.XPATH, "//*[@id='contextualHelp']/div/div[2]/nav/button"))
            )

            # dismiss initial helper dialog
            driver.execute_script(JS_CLICK, popup_next_button)
            driver.execute_script(JS_CLICK, popup_next_button)

        began_constructing = press_construct_building_button_for(driver, building)
        if began_constructing:
            break

    print(f"Successfully began constructing {building} in slot {building_slot}")


def wall_built(driver):
    navigate_to_buildings(driver)

    building_slot = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.XPATH, "//*[@id='villageContent']/div[22]"))
    )

    if building_slot.get_attribute('data-name'):
        return True
    return False


def construct_wall(driver):
    navigate_to_buildings(driver)

    building_slot = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.XPATH, "//*[@id='villageContent']/div[22]"))
    )

    if not can_build(building_slot):
        return

    driver.execute_script(JS_CLICK, building_slot) # use javascript to get around helper popup

    # wall is the only building allowed in slot 40, build button for it will be the only one that exists on the page
    try:
        build_button = driver.find_element(By.CSS_SELECTOR, '.textButtonV1.green.new')
        build_button.click()
    except NoSuchElementException:
        print("Wall has already been constructed!")

# %%
def upgrade_mission_clay_field(driver):
    navigate_to_resource_fields(driver)

    building_slot = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.XPATH, "//a[contains(@href, '/build.php?id=5')]"))
    )

    if not can_build(building_slot):
        return

    driver.execute_script(JS_CLICK, building_slot) # use javascript to get around helper popup

    button_upgrade = driver.find_element(By.CSS_SELECTOR, '.textButtonV1.green.build')
    if '2' in button_upgrade.text:
        button_upgrade.click()
    else:
        print("Clay field already at lvl 2.")


def run_missions_and_disable_contextual_helpers(driver):
    disable_contextual_help(driver)
    upgrade_mission_clay_field(driver)
    construct_building_in_slot(driver, 'Cranny', 30)
    construct_wall(driver)
    dismiss_report_helper_popup(driver)
    dismiss_ok_popup(driver)

# %%
# TODO: Func is error prone, revisit and reimplement
def get_resources_from_hero(driver, resource_type=-1):
    resources_to_get = [resource_type]
    if resource_type == -1:
        resources_to_get = [WOOD, CLAY, IRON, WHEAT]
    
    navigate_to_hero_inventory(driver)

    for resource_id in resources_to_get:
        amount_to_collect = 0

        # if we have all res types, max res index will be iron at position 4, no need to go beyond this
        for i in range(1, 5):
            item = driver.find_element(By.CSS_SELECTOR, f'.heroItems.filter_all > div:nth-child({i})')
            item_type = item.find_element(By.XPATH, './div[1]').get_attribute('class')

            id_str = ''.join(filter(str.isdigit, item_type))
            item_id = int(id_str) if id_str else -1
            
            if item_id == 144 + resource_id: # if item ID matches resource type
                # TODO: clicks failing on these pages for unknown reason, using js to avoid errors
                driver.execute_script(JS_CLICK, item)

                try:
                    input_amount = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
                        (By.XPATH, '//*[@id="consumableHeroItem"]/label/input'))
                    )
                    time.sleep(0.3) # wait to allow time for value to load
                    amount = driver.execute_script("return arguments[0].value;", input_amount)
                    #amount = input_amount.get_attribute('value')
                except StaleElementReferenceException:
                    continue

                amount_to_collect = int(int(amount) * 0.7) # only get 80% of total amount to prevent filling warehouses

                input_amount.clear()
                driver.execute_script("arguments[0].value = arguments[1];", input_amount, str(amount_to_collect))
                #input_amount.send_keys(str(amount_to_collect))

                
                button_transfer = driver.find_element(
                    By.CSS_SELECTOR, '.textButtonV2.buttonFramed.rectangle.withText.green'
                )

                time.sleep(1) # wait to allow time for value to load
                driver.execute_script(JS_CLICK, button_transfer)

                print(f"Successfully collected resource {resource_id} (amount={amount_to_collect}) from hero.")
                break

        print(f"Unable to collect resource {resource_id} from hero.")

# %%
''' resource field upgrade job '''

'''
def can_afford_resource_field_upgrade(driver):
    navigate_to_resource_fields(driver)

    resource_field_container = driver.find_element(By.XPATH, '//*[@id="resourceFieldContainer"]')
    resource_field_links = resource_field_container.find_elements(By.TAG_NAME, 'a')

    
    num_res_fields = len(resource_field_links)
    for i in range(2, num_res_fields + 1): # start at 2 to skip village center
        link = driver.find_element(By.XPATH, f'//*[@id="resourceFieldContainer"]/a[{i}]')
        if 'good' in link.get_attribute('class'):
            return True

        # Use ActionChains to move to the element and hover over it
        ActionChains(driver).move_to_element(link).perform()

        # Now retrieve the aria-describedby attribute
        aria_describedby_id = link.get_attribute('aria-describedby')

        # If the aria-describedby attribute points to an element's ID, you can then find this element
        if aria_describedby_id:
            try:
                requirements_info = driver.find_element(By.ID, aria_describedby_id).text.split('\n')
                resource_requirements = [int(item) for item in requirements_info if item.isdigit()]
            except NoSuchElementException:
                continue

            print(resource_requirements)
            if not resource_requirements:
                continue

            can_afford = True
            for i in range(4): # only need resource counts, given in order of: wood, clay, iron, wheat
                resources_available = driver.find_element(By.XPATH, f'//*[@id="l{i + 1}"]') # IDs go from l1 - l4
                resources_available = int(resources_available.text.replace(',', ''))

                if resources_available < resource_requirements[i]:
                    can_afford = False

            # if we have enough resources of all types for current field, we can afford it
            if can_afford:
                body = driver.find_element(By.TAG_NAME, 'body')
                ActionChains(driver).move_to_element(body).perform() # stop hovering
                time.sleep(0.2)
                return True

    # if we were unable to find a field we could afford
    body = driver.find_element(By.TAG_NAME, 'body')
    ActionChains(driver).move_to_element(body).perform() # stop hovering
    time.sleep(0.2)
    return False
'''


def find_lowest_level_field_of_type(driver, gid):
    navigate_to_resource_fields(driver)

    resource_field_container = driver.find_element(By.CSS_SELECTOR, '#resourceFieldContainer')
    resource_field_links = resource_field_container.find_elements(By.TAG_NAME, 'a')
    num_res_fields = len(resource_field_links)

    target_fields = []
    for i in range(2, num_res_fields + 1): # start at 2 to skip village center
        link = driver.find_element(By.XPATH, f'//*[@id="resourceFieldContainer"]/a[{i}]')
        if 'good' in link.get_attribute('class') and f'gid{gid}' in link.get_attribute('class'):
            target_fields.append(link)

    lowest_level_field = None
    lowest_level = 999

    for field in target_fields:
        if 'underConstruction' in field.get_attribute('class'):
            continue

        curr_level = int(field.find_element(By.XPATH, './div').text.strip() or 0)
        if curr_level < lowest_level:
            lowest_level_field = field
            lowest_level = curr_level

    return lowest_level_field


def attempt_to_upgrade_lowest_level_field(drivers_info, driver, scheduler=None, retry_attempts=1):
    navigate_to_resource_fields(driver)

    try: # check if building queue is full before attempting field upgrade, skip if queue full
        building_list = driver.find_element(By.CSS_SELECTOR, '.buildingList')
        buildings_being_built = building_list.find_elements(By.TAG_NAME, 'li')

        if (not drivers_info[driver]['Gold Club'] and len(buildings_being_built) >= 1) or \
           (    drivers_info[driver]['Gold Club'] and len(buildings_being_built) >= 2):
            logs[f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}'] = \
                "Unable to upgrade resource field! Building queue full, skipping upgrade attempt."
            
            if scheduler:
                scheduler.add_job(attempt_to_upgrade_lowest_level_field, 'interval',
                                  seconds=calc_new_interval_between(343, 907),
                                  id=f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}',
                                  args=[drivers_info, driver, scheduler], replace_existing=True)

            return

    except NoSuchElementException:
        logs[f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}'] = "Nothing currently being built, proceeding."

    lowest_level_field = None
    lowest_level = 999
    gid_types = [WOOD, CLAY, IRON, WHEAT]  # List of gid types you want to check

    for gid in gid_types:
        field = find_lowest_level_field_of_type(driver, gid)
        if field:
            curr_level = int(field.find_element(By.XPATH, './div').text.strip() or 0)
            if curr_level < lowest_level:
                lowest_level_field = field
                lowest_level = curr_level

    if lowest_level_field:
        lowest_level_field.click()

        button_upgrade = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.textButtonV1.green.build'))
        )
        button_upgrade.click()

        logs[f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}'] = "Began upgrading resource field."
    else: # if no available fields to upgrade, none can be afforded
        #if not can_afford_resource_field_upgrade(driver):
        #if retry_attempts > 0:
        logs[f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}'] = "Not enough resources to upgrade!"
        #logs[f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}'] = "Not enough resources to upgrade! Refilling resources and trying again."
        #get_resources_from_hero(driver)
        #attempt_to_upgrade_lowest_level_field(drivers_info, driver, scheduler, retry_attempts - 1)

    if scheduler:
        scheduler.add_job(attempt_to_upgrade_lowest_level_field, 'interval',
                          seconds=calc_new_interval_between(343, 907),
                          id=f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}',
                          args=[drivers_info, driver, scheduler], replace_existing=True)

# %%
''' war jobs '''


def convert_timer_time_to_seconds(time_str): # in format of HH:MM:SS
    # Parse the time string into a datetime object
    time = datetime.strptime(time_str, "%H:%M:%S")

    # Extract hours, minutes, and seconds and convert to total seconds
    seconds = time.hour * 3600 + time.minute * 60 + time.second
    return seconds



def incoming_attack(drivers_info, driver, scheduler):

    navigate_to_resource_fields(driver)

    try:
        troop_movements_container = driver.find_element(By.ID, 'movements')
    except NoSuchElementException:
        logs[f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}'] = "No troop movements found."
        
        scheduler.add_job(incoming_attack, 'interval',
                          seconds=calc_new_interval_between(678, 876),
                          id=f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}',
                          args=[drivers_info, driver, scheduler], replace_existing=True)
        
        return
    
    try:
        incoming_troops_row = troop_movements_container.find_element(By.XPATH, ".//th[contains(text(), 'Incoming')]")
    except NoSuchElementException:
        logs[f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}'] = "No incoming troops found."

        scheduler.add_job(incoming_attack, 'interval',
                          seconds=calc_new_interval_between(678, 876),
                          id=f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}',
                          args=[drivers_info, driver, scheduler], replace_existing=True)

        return

    troop_movements_rows = troop_movements_container.find_elements(By.TAG_NAME, 'tr')
    for troop_movement in troop_movements_rows:
        try:
            th = troop_movement.find_element(By.TAG_NAME, 'th')
            if 'Outgoing' in th.text: # if we've hit the Outgoing Troops row/section, we're done
                break
            else: # else this is the Incoming Troops row, skip it
                continue
        except NoSuchElementException: # if no th element found, this is a troop movement
            pass

        try:
            img = troop_movement.find_element(By.XPATH, './td/a/img')
        except NoSuchElementException:
            logs[f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}'] = "No image found."
            continue

        if 'att1' in img.get_attribute('class'):
            timer = troop_movement.find_element(By.CSS_SELECTOR, '.timer')
            seconds_till_attack = convert_timer_time_to_seconds(timer.text)

            logs[f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}'] = "Incoming attack found! Setting job to spend all resources before attack lands."
            
            scheduler.add_job(spend_all_resources_on_troop_production, 'date',
                              run_date=datetime.now() + timedelta(seconds=seconds_till_attack - 120),
                              id=f'{drivers_info[driver]["Username"]}_{SPEND_ALL_RESOURCES}',
                              args=[drivers_info, driver], replace_existing=True)

            return True, seconds_till_attack

    logs[f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}'] = "No incoming attacks!"

    scheduler.add_job(incoming_attack, 'interval',
                      seconds=calc_new_interval_between(678, 876),
                      id=f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}',
                      args=[drivers_info, driver, scheduler], replace_existing=True)

    return False, -1


def outgoing_attack(drivers_info, driver, scheduler):
    navigate_to_resource_fields(driver)

    try:
        troop_movements_container = driver.find_element(By.ID, 'movements')
    except NoSuchElementException:
        print("No troop movements found.")
        return
    
    try:
        outgoing_troops_row = troop_movements_container.find_element(By.XPATH, ".//th[contains(text(), 'Outgoing')]")
    except NoSuchElementException:
        print("No outgoing troops found.")
        return

    troop_movements_rows = troop_movements_container.find_elements(By.TAG_NAME, 'tr')
    outgoing_troops_start_index = next((i for i, element in enumerate(troop_movements_rows) if 'test' in element.text), None)
    for troop_movement in troop_movements_rows[outgoing_troops_start_index + 1]:    
        try:
            img = troop_movement.find_element(By.TAG_NAME, 'img')
        except NoSuchElementException:
            continue

        if 'def2' in img.get_attribute('class'):
            timer = troop_movement.find_element(By.CSS_SELECTOR, '.timer')
            seconds_till_attack = convert_timer_time_to_seconds(timer.text)

            print(f"Reinforcements incoming in {seconds_till_attack} seconds.")

            return True, seconds_till_attack

    print("No reinforcements coming.")
    return False, -1


def spend_all_resources_on_troop_production(drivers_info, driver):
    train_troops(drivers_info, driver, drivers_info[driver]['Troop Building'], drivers_info[driver]['Troop Name'], True)


def train_troops(drivers_info, driver, building, troop_name, incoming_attack_imminent=False, scheduler=None):
    enter_building(driver, building)

    try:
        link_troop_name = driver.find_element(By.XPATH, f"//a[contains(text(), '{troop_name}')]")
    except NoSuchElementException:
        logs[f'{drivers_info[driver]["Username"]}_{TRAIN_TROOPS}'] = \
            "Troop not found. Please check troop name and spelling."
    target_troop_container = link_troop_name.find_element(By.XPATH, '../../..')

    if incoming_attack_imminent:
        button_exchange_resources = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(
            (By.XPATH, '//button[contains(text(), "Exchange resources")]'))
        )
        button_exchange_resources.click()

        button_distribute_remaining_resources = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(
            (By.XPATH, '//button[contains(text(), "Distribute remaining resources")]'))
        )
        button_distribute_remaining_resources.click()

        button_redeem = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(
            (By.XPATH, '//button[contains(text(), "Redeem")]'))
        )
        button_redeem.click()

        time.sleep(1) # allow page time to refresh after resource distribution

        try: #re-init troop container to avoid stale references
            link_troop_name = driver.find_element(By.XPATH, f"//a[contains(text(), '{troop_name}')]")
        except NoSuchElementException:
            logs[f'{drivers_info[driver]["Username"]}_{TRAIN_TROOPS}'] = \
                "Troop not found. Please check troop name and spelling."
        target_troop_container = link_troop_name.find_element(By.XPATH, '../../..')

    try: # div container changes when trainable troops is 0
        input_num_troops_to_train = target_troop_container.find_element(By.XPATH, './div[2]/div[4]/input')
    except NoSuchElementException:
        logs[f'{drivers_info[driver]["Username"]}_{TRAIN_TROOPS}'] = "Cannot afford to train any troops!"
        if scheduler:
            scheduler.add_job(train_troops, 'interval', seconds=calc_new_interval_between(10720, 13835),
                              id=f'{drivers_info[driver]["Username"]}_{TRAIN_TROOPS}', args=[drivers_info, driver, building, troop_name, False, scheduler],
                              replace_existing=True)
        return
    
    max_trainable = target_troop_container.find_element(By.XPATH, "./div[2]/div[4]/a").text
    max_trainable = int(max_trainable)

    input_num_troops_to_train.clear()
    input_num_troops_to_train.send_keys(max_trainable)

    button_start_training = driver.find_element(By.ID, 's1')
    button_start_training.click()

    logs[f'{drivers_info[driver]["Username"]}_{TRAIN_TROOPS}'] = f"Successfully began training {max_trainable} {troop_name}."

    if scheduler:
        scheduler.add_job(train_troops, 'interval', seconds=calc_new_interval_between(1720, 3835),
                          id=f'{drivers_info[driver]["Username"]}_{TRAIN_TROOPS}', args=[drivers_info, driver, building, troop_name, False, scheduler],
                          replace_existing=True)


def check_total_troop_counts():
    pass


def activate_farm_list_raids_for(list_id, driver, distance_limit=float('inf'), ignore_curr_state=False):
    try: # noob protection will be first div in "rallyPointFarmList" until shield wears off
        list_element_xpath = f'//*[@id="rallyPointFarmList"]/div[1]/div[{list_id + 1}]'
        list_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, list_element_xpath)))
    except TimeoutException: # use second div if first is noob protection info.
        list_element_xpath = f'//*[@id="rallyPointFarmList"]/div[2]/div[{list_id + 1}]'
        list_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, list_element_xpath)))

    name = list_element.find_element(By.XPATH, './div/div[1]/div[2]/div[1]').text

    table = list_element.find_element(By.XPATH, './div/div[2]/table')
    table_body = table.find_element(By.XPATH, './tbody')
    table_footer = table.find_element(By.XPATH, './tfoot')
    table_rows = table_body.find_elements(By.TAG_NAME, 'tr')

    boxes_to_click_ids = []
    for row_index in range(1, len(table_rows)): # purposefully removed last index to skip "Add target" row
        row_xpath = f'{list_element_xpath}/div/div[2]/table/tbody/tr[{row_index}]'
        try:
            row = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, row_xpath)))
        except TimeoutException:
            break

        checkbox_xpath = None
        try:
            checkbox = row.find_element(By.XPATH, './td[1]/label/input')
            checkbox_xpath = row_xpath + '/td[1]/label/input'
            driver.execute_script(JS_SCROLL_INTO_VIEW, checkbox)
        except NoSuchElementException:
            continue

        curr_state_container = row.find_element(By.CSS_SELECTOR, '.state')
        currently_attacking = False
        try:
            curr_state = curr_state_container.find_element(By.TAG_NAME, 'i')
            if 'attack_small' in curr_state.get_attribute('class'):
                currently_attacking = True
        except NoSuchElementException:
            currently_attacking = False

        dist_container = row.find_element(By.CSS_SELECTOR, '.distance')
        dist = float(dist_container.find_element(By.XPATH, './span').text)
        if dist > distance_limit:
            break

        num_troops_container = row.find_element(By.CSS_SELECTOR, '.troops')
        num_troops = int(num_troops_container.find_element(By.XPATH, './div[1]/span[1]/span[1]').text)

        try:
            filthy_nominator = driver.find_element(By.XPATH, f'{list_element_xpath}/div/div[2]/table/tfoot/tr[1]/td[2]/div/div/span/span/span[1]').text
            filthy_denominator = driver.find_element(By.XPATH, f'{list_element_xpath}/div/div[2]/table/tfoot/tr[1]/td[2]/div/div/span/span/span[1]').text
            nominator   = int(re.sub(r'[^\d]', '', filthy_nominator))
            denominator = int(re.sub(r'[^\d]', '', filthy_denominator))
        except NoSuchElementException:
            nominator = denominator = None
        
        target = row.find_element(By.CSS_SELECTOR, '.target')
        target_link = target.find_element(By.XPATH, './a')

        last_raid_state_container = row.find_element(By.CSS_SELECTOR, '.lastRaid')
        prev_attack_suffered_losses = False
        try:
            last_raid_state = last_raid_state_container.find_element(By.TAG_NAME, 'i')
            if 'attack_won_withoutLosses_small' not in last_raid_state.get_attribute('class'):
                prev_attack_suffered_losses = True
        except NoSuchElementException:
            prev_attack_suffered_losses = False

        if (not currently_attacking or ignore_curr_state) and \
        (not prev_attack_suffered_losses or (name.lower() == 'oases' and not oases_has_troops(driver, target_link))) and \
        ((not nominator and not denominator) or nominator + num_troops <= denominator):
            boxes_to_click_ids.append(checkbox_xpath)
        
    for id in boxes_to_click_ids:
        try:
            checkbox = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, id)))
            driver.execute_script(JS_SCROLL_INTO_VIEW, checkbox)
        except NoSuchElementException:
            continue

        checkbox.click()

    # start raids
    if boxes_to_click_ids:
        list_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, list_element_xpath)))
        button_start_raids = list_element.find_element(By.XPATH, './div/div[1]/button')
        driver.execute_script(JS_SCROLL_INTO_VIEW, button_start_raids)
        button_start_raids.click()


def has_gold_club_membership(drivers_info, driver, scheduler=None):
    enter_building(driver, 'Rally Point')
    
    try:
        button_farm_list = driver.find_element(By.XPATH, '//a[contains(@href, "/build.php?id=39&gid=16&tt=99")]')
        button_farm_list.click()

        if scheduler and scheduler.get_job(f'{drivers_info[driver]["Username"]}_{GOLD_CLUB_CHECK}'):
            scheduler.remove_job(f'{drivers_info[driver]["Username"]}_{GOLD_CLUB_CHECK}')

        return True
    except NoSuchElementException:
        log_msg = "Please activate Travian Gold Club to gain access to farm lists."
        logs[f'{drivers_info[driver]["Username"]}_{GOLD_CLUB_CHECK}'] = log_msg
        logs[f'{drivers_info[driver]["Username"]}_{RAIDS}'] = log_msg
        
        if scheduler:
            scheduler.add_job(has_gold_club_membership, 'interval', seconds=calc_new_interval_between(604, 932),
                              id=f'{drivers_info[driver]["Username"]}_{GOLD_CLUB_CHECK}',
                              args=[drivers_info, driver, scheduler], replace_existing=True)
        
        return False


def oases_has_troops(driver, target):
    target.click()

    try:
        first_troop_row = WebDriverWait(driver, 10).until(EC.presence_of_element_located(
            (By.XPATH, '//*[@id="troop_info"]/tbody/tr[1]/td'))
        )
        has_troops = (first_troop_row.text != 'none')
    except TimeoutException:
        has_troops = True

    driver.back()
    return has_troops

  

def send_troops_to_farm(drivers_info, driver, scheduler=None):
    if 'build.php?id=39&gid=16&tt=99' not in driver.current_url:
        enter_building(driver, 'Rally Point')

        try:
            button_farm_list = driver.find_element(By.XPATH, '//a[contains(@href, "/build.php?id=39&gid=16&tt=99")]')
            button_farm_list.click()
        except NoSuchElementException:
            logs[f'{drivers_info[driver]["Username"]}_{RAIDS}'] = "Please activate Travian Gold Club to gain access to farm lists."
            if scheduler:
                scheduler.pause_job(job_id=f'{drivers_info[driver]["Username"]}_{RAIDS}')
            return


    try:
        farm_lists_container = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.villageWrapper'))
        )
    except TimeoutException:
        logs[f'{drivers_info[driver]["Username"]}_{RAIDS}'] = "Please create a farm list to begin raiding!"
        if scheduler:
            scheduler.pause_job(job_id=f'{drivers_info[driver]["Username"]}_{RAIDS}')
        return

    farm_lists = farm_lists_container.find_elements(By.CSS_SELECTOR, '.dropContainer')
    for farm_list in farm_lists:
        name = farm_list.find_element(By.XPATH, './div/div[1]/div[2]/div[1]').text

        farm_list_index = driver.execute_script("return Array.prototype.indexOf.call(arguments[0].parentNode.children, arguments[0]);", farm_list)
        activate_farm_list_raids_for(farm_list_index, driver, distance_limit=7, ignore_curr_state=False)
        
        logs[f'{drivers_info[driver]["Username"]}_{RAIDS}'] = f'Finished raid logic for {name}'


    logs[f'{drivers_info[driver]["Username"]}_{RAIDS}'] = "Finished raid attempt."

    if scheduler:
        scheduler.add_job(send_troops_to_farm, 'interval', seconds=calc_new_interval_between(548, 878),
                          id=f'{drivers_info[driver]["Username"]}_{RAIDS}',
                          args=[drivers_info, driver, scheduler], replace_existing=True)

# %%
''' mission/daily rewards collection jobs '''

def collect_mission_resources(drivers_info, driver, scheduler=None):
    # button should exist on all pages, if not we've encountered an error. Refresh page and try again
    try:
        button_mentor = driver.find_element(By.ID, 'questmasterButton')
    except NoSuchElementException:
        driver.refresh()
        button_mentor = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
            (By.ID, 'questmasterButton'))
        )

    try:
        speech_bubble = button_mentor.find_element(By.XPATH, './div')
    except NoSuchElementException:
        logs[f'{drivers_info[driver]["Username"]}_{COLLECT_MISSION_RESOURCES}'] = "No mission resources to collect!"
        if scheduler:
            scheduler.add_job(collect_mission_resources, 'interval', seconds=calc_new_interval_between(343, 907),
                              id=f'{drivers_info[driver]["Username"]}_{COLLECT_MISSION_RESOURCES}', 
                              args=[drivers_info, driver, scheduler], replace_existing=True)
        return

    button_mentor.click()

    task_overview = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.taskOverview')))    

    task_list = task_overview.find_elements(By.XPATH, './div')
    for task in task_list:
        if 'achieved' in task.get_attribute('class'):
            button_collect = task.find_element(By.TAG_NAME, 'button')
            button_collect.click()
    

    logs[f'{drivers_info[driver]["Username"]}_{COLLECT_MISSION_RESOURCES}'] = "Successfully collected mission resources."
    if scheduler:
        scheduler.add_job(collect_mission_resources, 'interval', seconds=calc_new_interval_between(343, 907),
                          id=f'{drivers_info[driver]["Username"]}_{COLLECT_MISSION_RESOURCES}',
                          args=[drivers_info, driver, scheduler], replace_existing=True)


def collect_daily_quests_rewards(drivers_info, driver, scheduler=None):
    button_daily_quests = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.XPATH, '//*[@id="navigation"]/a[7]'))
    )

    try:
        indicator = button_daily_quests.find_element(By.XPATH, './div')
    except NoSuchElementException:
        logs[f'{drivers_info[driver]["Username"]}_{COLLECT_DAILY_QUEST_REWARDS}'] = "No rewards to collect!"
        if scheduler:
            scheduler.add_job(collect_daily_quests_rewards, 'interval',
                              seconds=calc_new_interval_between(24112, 43022),
                              id=f'{drivers_info[driver]["Username"]}_{COLLECT_DAILY_QUEST_REWARDS}',
                              args=[drivers_info, driver, scheduler], replace_existing=True)
        return

    button_daily_quests.click()

    achievement_reward_list = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.ID, 'achievementRewardList'))
    )
    reward_containers = achievement_reward_list.find_elements(By.CSS_SELECTOR, '.achievement')
    for container in reward_containers:
        try:
            reward_ready_icon = container.find_element(By.CSS_SELECTOR, '.bigSpeechBubble.rewardReady')
        except NoSuchElementException:
            logs[f'{drivers_info[driver]["Username"]}_{COLLECT_DAILY_QUEST_REWARDS}'] = "Reward not ready!"
            continue

        container.click()

        button_collect_reward = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.textButtonV1.green.questButtonGainReward')))
        button_collect_reward.click()

    logs[f'{drivers_info[driver]["Username"]}_{COLLECT_DAILY_QUEST_REWARDS}'] = "Successfully collected mission resources."
    
    if scheduler:
        scheduler.add_job(collect_daily_quests_rewards, 'interval', seconds=calc_new_interval_between(24112, 43022),
                          id=f'{drivers_info[driver]["Username"]}_{COLLECT_DAILY_QUEST_REWARDS}',
                          args=[drivers_info, driver, scheduler], replace_existing=True)

# %%
''' hero jobs '''

def attempt_to_start_adventure(drivers_info, driver, scheduler=None):
    # hero button should exist on all pages, if not we've encountered an error. Refresh page and try again
    try:
        button_hero_status = driver.find_element(By.XPATH, '//*[@id="topBarHero"]/div/a/i')
    except NoSuchElementException:
        driver.refresh()
        button_hero_status = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//*[@id="topBarHero"]/div/a/i')))


    # dynamic ID, using href to reference
    button_adventures = driver.find_element(By.XPATH, "//a[@href='/hero/adventures']")
    try:
        num_adventures = button_adventures.find_element(By.XPATH, "./div")
    except NoSuchElementException:
        num_adventures = None

    if num_adventures and 'heroHome' in button_hero_status.get_attribute('class') and int(num_adventures.text) > 0:
        button_adventures.click()

        button_start_first_adventure = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
            (By.XPATH, '//*[@id="heroAdventure"]/table/tbody/tr[1]/td[5]/button'))
        )
        button_start_first_adventure.click()

        button_continue = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//*[@id="heroAdventure"]/div/button')))
        button_continue.click()

        logs[f'{drivers_info[driver]["Username"]}_{ADVENTURES}'] = "Successfully sent out hero on adventure!"
    elif num_adventures is None:
        logs[f'{drivers_info[driver]["Username"]}_{ADVENTURES}'] = "No adventures found."
    elif 'heroRunning' in button_hero_status.get_attribute('class'):
        logs[f'{drivers_info[driver]["Username"]}_{ADVENTURES}'] = "Hero is already on an adventure!"
    else:
        logs[f'{drivers_info[driver]["Username"]}_{ADVENTURES}'] = "Error attempting to start adventure."
    
    if scheduler:
        scheduler.add_job(attempt_to_start_adventure, 'interval', seconds=calc_new_interval_between(307, 902),
                          id=f'{drivers_info[driver]["Username"]}_{ADVENTURES}', args=[drivers_info, driver, scheduler],
                          replace_existing=True)


# possible options are 'resourceProduction', 'fightingStrength', 'offBonus', 'defBonus
def upgrade_hero(drivers_info, driver, scheduler=None, attribute_to_upgrade='resourceProduction'):
    level_up_icon = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.XPATH, '//*[@id="topBarHero"]/i'))
    )
    
    if 'show' not in level_up_icon.get_attribute('class'):
        logs[f'{drivers_info[driver]["Username"]}_{HERO_UPGRADE}'] = "Hero has no points to spend!"
        if scheduler:
            #scheduler.pause_job(job_id=f'{drivers_info[driver]["Username"]}_{HERO_UPGRADE}')
            scheduler.add_job(upgrade_hero, 'interval', seconds=calc_new_interval_between(12542, 24333),
                              id=f'{drivers_info[driver]["Username"]}_{HERO_UPGRADE}',
                              args=[drivers_info, driver, scheduler],
                              replace_existing=True)
        return
    
    navigate_to_hero_inventory(driver)

    button_attributes = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.XPATH, '//*[@id="heroV2"]/div[1]/div[1]/div/div[2]'))
    )
    button_attributes.click()

    input_points = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
        (By.NAME, attribute_to_upgrade))
    )
    curr_num_points = int(input_points.get_attribute('value'))
    new_num_points = curr_num_points + 4 # hero always gets 4 points to spend after leveling up
    
    input_points.clear()
    input_points.send_keys(str(new_num_points))

    button_save_changes = driver.find_element(By.ID, 'savePoints')
    time.sleep(1) # button click doesn't register if we move too fast
    button_save_changes.click()

    logs[f'{drivers_info[driver]["Username"]}_{HERO_UPGRADE}'] = f"Successfully upgraded hero and spent points on {attribute_to_upgrade}."

    if scheduler:
        scheduler.add_job(upgrade_hero, 'interval', seconds=calc_new_interval_between(12542, 24333),
                          id=f'{drivers_info[driver]["Username"]}_{HERO_UPGRADE}',
                          args=[drivers_info, driver, scheduler],
                          replace_existing=True)

# %%
# TODO: Update table generation to handle multiple drivers
def generate_job_scheduler_table_from(drivers_info, scheduler):
    layout = Layout()

    now = datetime.now(timezone.utc)

    # Sort the jobs by job.id and then by countdown
    jobs = scheduler.get_jobs()
    sorted_jobs = sorted(jobs, key=lambda job: (
        job.id,
        999 if job.next_run_time is None else (job.next_run_time - now).total_seconds()
    ))

    for driver in drivers_info.keys():
        drivers_info[driver]['Table'] = Table(title=f"{drivers_info[driver]['Username']}'s Scheduled Jobs",
                                              box=box.DOUBLE, safe_box=False)
        drivers_info[driver]['Table'].width = 100

    layout = Layout()
    layout.split_column(*[drivers_info[driver]['Table'] for driver in drivers_info.keys()])

    for driver in drivers_info.keys():
        drivers_info[driver]['Table'].add_column("Job ID", style="cyan", no_wrap=True)
        drivers_info[driver]['Table'].add_column("Next Run At", style="magenta")
        drivers_info[driver]['Table'].add_column("Countdown", style="green")
        drivers_info[driver]['Table'].add_column("Log", style="blue")

        for job in sorted_jobs:
            if drivers_info[driver]['Username'] in job.id:
                next_run = job.next_run_time
                countdown = 999 if next_run is None else (next_run - now).total_seconds()
                drivers_info[driver]['Table'].add_row(job.id, str(next_run), str(int(countdown)), logs.get(job.id, ''))
        
    return layout

# %%
''' TESTING BLOCK

driver = init_webdriver()
drivers_info = {
    driver: {
        'Username': 'daniel.doza',
        'Type': 'Enforcer',
        'Port': None,
        'Troop Building': 'Barracks',
        'Troop Name': 'Clubswinger',
    }
}

attempt_login('https://ts2.x1.international.travian.com', drivers_info[driver]['Username'], 'Tomorrow2040!', driver)

with managed_scheduler() as scheduler:
    # enter function to test here
    incoming_attack(drivers_info, driver, scheduler) 

    with Live(generate_job_scheduler_table_from(drivers_info, scheduler), refresh_per_second=1, console=console, vertical_overflow='visible', screen=True) as live:
        try:
            while True:
                live.update(generate_job_scheduler_table_from(drivers_info, scheduler), refresh=True)

                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass
'''

# %%
''' init. and login to server (single account)
input_site = 'https://ts2.x1.international.travian.com/dorf1.php'
#input_site = input("Site:") # Commented out while testing

input_port = input("Port:")

# !!! NO PROXY ADDED TO MANAGED_WEBDRIVER FUNC, ENSURE PROXY PORT USED TO SETUP ACCOUNT IS ADDED HERE TO AVOID BANS
try:
    with managed_scheduler() as scheduler, managed_webdriver(input_port) as driver:
        drivers_info = {
            driver: {
                'Username': input("Username:"),
                'Type': input("Account type:"),
                'Port': input_port,
                'Troop Building': input("Troop Building:"),
                'Troop Name': input("Troop Name:"),
            }
        }
        input_password = getpass("Password:")

        if drivers_info[driver]['Username'] and drivers_info[driver]['Type'] and drivers_info[driver]['Port'] and \
            input_password:
            drivers_info[driver]['Gold Club'] = has_gold_club_membership(drivers_info, driver, scheduler=None)

            attempt_login(input_site, drivers_info[driver]['Username'], input_password, driver)

            # !!! STILL IN TESTING, will fail without restarting once building queue is full
            #if not wall_built(driver):
            #    run_missions_and_disable_contextual_helpers(driver)

            scheduler.add_job(attempt_to_start_adventure, 'interval', seconds=7,
                              id=f'{drivers_info[driver]["Username"]}_{ADVENTURES}', args=[drivers_info, driver, scheduler])
            scheduler.add_job(upgrade_hero, 'interval', seconds=15,
                              id=f'{drivers_info[driver]["Username"]}_{HERO_UPGRADE}', args=[drivers_info, driver, scheduler])
            scheduler.add_job(collect_mission_resources, 'interval', seconds=24,
                              id=f'{drivers_info[driver]["Username"]}_{COLLECT_MISSION_RESOURCES}', args=[drivers_info, driver, scheduler])
            scheduler.add_job(collect_daily_quests_rewards, 'interval', seconds=32,
                              id=f'{drivers_info[driver]["Username"]}_{COLLECT_DAILY_QUEST_REWARDS}', args=[drivers_info, driver, scheduler])
            scheduler.add_job(incoming_attack, 'interval', seconds=32,
                              id=f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}', args=[drivers_info, driver, scheduler])
            if drivers_info[driver]['Gold Club']:
                scheduler.add_job(send_troops_to_farm, 'interval', seconds=42,
                                  id=f'{drivers_info[driver]["Username"]}_{RAIDS}', args=[drivers_info, driver, scheduler])
            if drivers_info[driver]['Type'].lower() == 'enforcer':
                scheduler.add_job(train_troops, 'interval', seconds=45,
                                  id=f'{drivers_info[driver]["Username"]}_{TRAIN_TROOPS}',
                                  args=[drivers_info, driver,
                                        drivers_info[driver]['Troop Building'], drivers_info[driver]['Troop Name'],
                                        False, scheduler])            
            else:
                scheduler.add_job(attempt_to_upgrade_lowest_level_field, 'interval', seconds=120,
                                id=f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}', args=[drivers_info, driver, scheduler])
            
            # for any uncaught server errors, refresh page every hour to ensure continued job executions
            scheduler.add_job(refresh_page, 'interval', seconds=600,
                                id=f"{drivers_info[driver]['Username']}_{REFRESH}", args=[drivers_info, driver, scheduler])

            with Live(generate_job_scheduler_table_from(drivers_info, scheduler), refresh_per_second=1, console=console) as live:
                try:
                    while True:
                        live.update(generate_job_scheduler_table_from(drivers_info, scheduler))
                        time.sleep(1)
                except (KeyboardInterrupt, SystemExit):
                    pass
except Exception as e:
    print(f"Error: {e}")
'''

# %%
''' init. and login to server (multiple accounts) '''
input_site = 'https://ts2.x1.international.travian.com/dorf1.php'
#input_site = input("Site:") # Commented out while testing

drivers_info = {}
user_info = {}

user_info = pd.read_excel('~/Dropbox/TravianAccounts.xlsx')
for index, row in user_info.iterrows():
    driver = init_webdriver(int(row['Port']) if not pd.isna(row['Port']) else None)
    attempt_login(input_site, row['Username'], row['Password'], driver)

    # !!! STILL IN TESTING, will fail without restarting once building queue is full
    #if not wall_built(driver):
    #    run_missions_and_disable_contextual_helpers(driver)

    drivers_info[driver] = row


'''
proxy_ports = [[None, 'enforcer'], [24000, 'leader'], [24001, 'enforcer'], [24002, 'enforcer'], [24003, 'sourcer'], [24004, 'defender']]
#for i in range(num_accounts): # get accounts info
#    proxy_port = 24000 + i
for proxy_port in proxy_ports:
    user_info[proxy_port[0]] = {}
    user_info[proxy_port[0]]['username'] = input(f"Username for proxy port {proxy_port[0]}:")
    user_info[proxy_port[0]]['password'] = getpass(f"Password for proxy port {proxy_port[0]}:")


#for i in range(num_accounts): # initialize web drivers
#    proxy_port = 24000 + i
for proxy_port in proxy_ports:
    driver = init_webdriver(proxy_port[0])
    attempt_login(input_site, user_info[proxy_port[0]]['username'], driver)

    # !!! STILL IN TESTING, will fail without restarting once building queue is full
    #if not wall_built(driver):
    #    run_missions_and_disable_contextual_helpers(driver)
    
    drivers[driver] = proxy_port[1]
'''


''' begin scheduler tasks '''
with managed_scheduler() as scheduler:
    for driver in drivers_info.keys():
        drivers_info[driver]['Gold Club'] = has_gold_club_membership(drivers_info, driver, scheduler=None)

        scheduler.add_job(attempt_to_start_adventure, 'interval', seconds=7,
                          id=f'{drivers_info[driver]["Username"]}_{ADVENTURES}', args=[drivers_info, driver, scheduler])
        scheduler.add_job(upgrade_hero, 'interval', seconds=14,
                          id=f'{drivers_info[driver]["Username"]}_{HERO_UPGRADE}', args=[drivers_info, driver, scheduler])
        scheduler.add_job(collect_mission_resources, 'interval', seconds=21,
                          id=f'{drivers_info[driver]["Username"]}_{COLLECT_MISSION_RESOURCES}', args=[drivers_info, driver, scheduler])
        scheduler.add_job(collect_daily_quests_rewards, 'interval', seconds=28,
                          id=f'{drivers_info[driver]["Username"]}_{COLLECT_DAILY_QUEST_REWARDS}', args=[drivers_info, driver, scheduler])
        scheduler.add_job(incoming_attack, 'interval', seconds=35,
                          id=f'{drivers_info[driver]["Username"]}_{CHECK_FOR_INCOMING_ATTACKS}', args=[drivers_info, driver, scheduler])
        if drivers_info[driver]['Upgrade Fields']:
            scheduler.add_job(attempt_to_upgrade_lowest_level_field, 'interval', seconds=42,
                              id=f'{drivers_info[driver]["Username"]}_{RESOURCE_FIELDS}', args=[drivers_info, driver, scheduler])
        if drivers_info[driver]['Type'].lower() == 'enforcer' and drivers_info[driver]['Train Troops']:
            scheduler.add_job(train_troops, 'interval', seconds=70,
                              id=f'{drivers_info[driver]["Username"]}_{TRAIN_TROOPS}',
                              args=[drivers_info, driver,
                                    drivers_info[driver]['Troop Building'], drivers_info[driver]['Troop Name'],
                                    False, scheduler])
        if drivers_info[driver]['Gold Club'] and drivers_info[driver]['Raid']:
            scheduler.add_job(send_troops_to_farm, 'interval', seconds=90,
                              id=f'{drivers_info[driver]["Username"]}_{RAIDS}', args=[drivers_info, driver, scheduler])

        # for any uncaught server errors, refresh page every hour to ensure continued job executions
        scheduler.add_job(refresh_page, 'interval', seconds=600,
                              id=f"{drivers_info[driver]['Username']}_{REFRESH}", args=[drivers_info, driver, scheduler])
    
    with Live(generate_job_scheduler_table_from(drivers_info, scheduler), refresh_per_second=1, console=console, vertical_overflow='visible', screen=True) as live:
        try:
            while True:
                live.update(generate_job_scheduler_table_from(drivers_info, scheduler), refresh=True)

                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass

for driver in drivers_info.keys():
    driver.quit()

run_command_in_background('curl -X POST "http://127.0.0.1:22999/api/shutdown"')

# %% [markdown]
# %%bash
# curl -X POST "http://127.0.0.1:22999/api/shutdown" # used to shutdown proxy-manager


