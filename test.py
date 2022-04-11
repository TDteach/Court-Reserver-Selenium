from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

import os
import json
import time
import pickle
from datetime import datetime

account_path = 'account.txt'
record_path = 'badminton_book'
url = 'https://connect.recsports.indiana.edu/booking'
st_time = datetime.strptime('7:00PM', '%I:%M%p')
ed_time = datetime.strptime('11:00PM', '%I:%M%p')
desired_time_interval = [(st_time, ed_time)]

driver = None

def main():
    global driver
    record = load_pickle_record(record_path)
    if record:
        last_update_time = record[-1]['update_time']
        if last_update_time.day == datetime.now().day:
            print('booked already')
            return

    # chrome binary should be installed first
    # '''bash
    # wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    # sudo dpkg -i google-chrome-stable_current_amd64.deb
    # google-chrome
    # '''
    options = webdriver.ChromeOptions()
    options.headless = True
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_window_size(1920, 1080)

    driver.get(url)
    driver.implicitly_wait(0.5)
    time.sleep(2)

    a = driver.find_elements(By.CLASS_NAME, 'container-link-text-item')
    for k, b in enumerate(a):
        if 'Badminton' in b.text:
            badminton_element = b
            print(k)
    badminton_element.click()
    driver.implicitly_wait(0.5)
    time.sleep(2)

    with open(account_path, "r") as f:
        data = f.readlines()
    username = data[0].split(':')[1].strip()
    password = data[1].split(':')[1].strip()
    login_with_IU_account(driver, username, password)
    time.sleep(2)

    duo_approved = False
    for k in range(15):
        try:
            book_date = select_last_day(driver)
        except:
            print('wait duo approved for %d seconds'%((k+1)*2))
            time.sleep(2)
            continue
        duo_approved = True
        break
    if not duo_approved:
        print("duo has not been approved!!")
        driver.quit()
        return
    if record and book_date <= record[-1]['book_date']: return
    if record is None: record = list()

    selected_keys = None

    court_order = [0,2,1]
    for k in court_order:
        court_botton_xpath = '//*[@id="tabBookingFacilities"]/button'
        court_bottons = driver.find_elements(By.XPATH, court_botton_xpath)
        cb = court_bottons[k]
        cb.click()
        driver.implicitly_wait(0.5)
        time.sleep(2)

        finer_court_xpath = court_botton_xpath + '[{}]/span'.format(k + 1)
        court_info = driver.find_element(By.XPATH, finer_court_xpath).text
        print(court_info)

        time_dict = list_available_time(driver)
        selected_keys = select_timeslot(time_dict)
        if selected_keys is not None:
            break

    if selected_keys is not None:
        book_time(selected_keys, driver)

        rd = {
            'book_date': book_date,
            'court_info': court_info,
            'booked_slots': list(),
            'update_time': datetime.now(),
        }
        for k in selected_keys:
            rd['booked_slots'].append((time_dict[k]['start_time'], time_dict[k]['end_time']))

        record.append(rd)
        print(record)
        save_pickle_record(record_path, record)
        save_json_record(record_path, record)
    else:
        print('have not found available time slots')

    driver.quit()


def login_with_IU_account(driver, username, password):
    # print(login_div[0].get_attribute('innerHTML'))
    time.sleep(2)
    login_button = driver.find_element(By.XPATH, '//*[@id="section-sign-in-first"]/div[@class="row mt-2"]/div/button')
    login_button.click()
    driver.implicitly_wait(0.5)
    time.sleep(2)

    username_blank = driver.find_element(By.ID, 'username')
    username_blank.send_keys(username)
    time.sleep(1)
    actions = ActionChains(driver)
    actions.send_keys(Keys.TAB)
    actions.send_keys(password)
    actions.perform()
    time.sleep(1)
    actions = ActionChains(driver)
    actions.send_keys(Keys.TAB)
    actions.send_keys(Keys.ENTER)
    actions.perform()

    driver.implicitly_wait(1)
    time.sleep(5)
    actions = ActionChains(driver)
    actions.send_keys(Keys.TAB)
    actions.send_keys(Keys.DOWN)
    actions.send_keys(Keys.TAB)
    actions.send_keys(Keys.ENTER)
    actions.perform()


def transfer_timestr(time_str):
    # print(time_str)
    time_conp = time_str.split(' ')
    if len(time_conp) == 4:
        a = [(0, 3), (2, 3)]
    elif len(time_conp) == 5:
        a = [(0, 1), (3, 4)]
    d_list = list()
    for aa in a:
        t_str = time_conp[aa[0]] + time_conp[aa[1]]
        if ':' not in t_str:
            f_str = '%I%p'
        else:
            f_str = '%I:%M%p'
        d = datetime.strptime(t_str, f_str)
        d_list.append(d)
    return d_list


def select_last_day(driver):
    time.sleep(1)

    button = driver.find_element(By.XPATH, '//*[@id="divBookingProducts-large"]/div[4]/a/div')
    button.click()

    driver.implicitly_wait(1)
    time.sleep(3)

    for _ in range(3):
        next_buttons = driver.find_elements(By.XPATH, '//*[@id="divBookingDateSelector"]/div[2]/div[2]/button')
        try:
            next_buttons[-1].click()
            time.sleep(1)
        except:
            break

    last_button = driver.find_elements(By.XPATH, '//*[@id="divBookingDateSelector"]/div[2]/div[2]/button')[-2]
    date_str = last_button.get_dom_attribute('data-date-text')
    book_date = datetime.strptime(date_str, '%b %d, %Y')
    last_button.click()
    driver.implicitly_wait(1)
    time.sleep(1)

    return book_date


def list_available_time(driver):
    base_xpath = '//*[@id="divBookingSlots"]/div[@class="d-flex row"]/div'
    time_slots = driver.find_elements(By.XPATH, base_xpath)
    # print(time_slots)
    rst_dict = dict()
    for k, t in enumerate(time_slots):
        finer_xpath = base_xpath + '[{}]/p/strong'.format(k + 1)
        z = driver.find_element(By.XPATH, finer_xpath)
        d = transfer_timestr(z.text)

        finer_xpath = base_xpath + '[{}]/div/button'.format(k + 1)
        av = 0
        try:
            z = driver.find_element(By.XPATH, finer_xpath)
            if 'Book' in z.text: av = 1
        except:
            pass

        _key = d[0].strftime('%H:%M')
        rst_dict[_key] = {'start_time': d[0], 'end_time': d[1], 'availabel': av, 'element': z}

    return rst_dict


def select_timeslot(time_dict):
    all_keys = list(time_dict.keys())
    all_keys.sort(key=lambda k: time_dict[k]['start_time'], reverse=True)

    selected_keys = None

    for begin_time, end_time in desired_time_interval:
        a = list()
        for k in all_keys:
            av = 0
            if begin_time <= time_dict[k]['start_time'] and time_dict[k]['end_time'] <= end_time:
                av = 1
            a.append(av & time_dict[k]['availabel'])
        for i in range(len(a) - 3):
            if sum(a[i:i + 3]) >= 3:
                if i + 4 <= len(a) and sum(a[i:i + 4]) >= 4:
                    selected_keys = all_keys[i:i + 4]
                else:
                    selected_keys = all_keys[i:i + 3]
                break
        if selected_keys is not None:
            break

    return selected_keys


def book_time(selected_keys, driver):
    if selected_keys is None:
        return

    actions = ActionChains(driver)
    actions.send_keys(Keys.PAGE_DOWN)
    actions.perform()
    driver.implicitly_wait(0.5)

    for k in selected_keys:
        time_dict = list_available_time(driver)
        e = time_dict[k]['element']
        e.click()
        driver.implicitly_wait(1)
        time.sleep(2)


def load_pickle_record(record_path):
    record_pickle_path = record_path + '.pkl'
    if not os.path.exists(record_pickle_path):
        return None
    with open(record_pickle_path, 'rb') as f:
        data = pickle.load(f)
    return data


def save_pickle_record(record_path, record):
    record_pickle_path = record_path + '.pkl'
    with open(record_pickle_path, 'wb') as f:
        pickle.dump(record, f)
    print('save pickle record to', record_pickle_path)


def save_json_record(record_path, record):
    json_record = list()
    for rd in record:
        js_rd = {
            'book_date': rd['book_date'].strftime('%b %d, %Y'),
            'court_info': rd['court_info'],
            'booked_slots': list(),
            'update_time': rd['update_time'].strftime('%b %d, %Y, %H:%M:%S'),
        }
        for st, ed in rd['booked_slots']:
            cb_str = st.strftime('%H:%M') + '->' + ed.strftime('%H:%M')
            js_rd['booked_slots'].append(cb_str)
        json_record.append(js_rd)
    record_json_path = record_path + '.json'
    with open(record_json_path, 'w') as f:
        json.dump(json_record, f, indent=4)
    print('save json record to', record_json_path)



def run():
    try:
        main()
    except Exception as e:
        print(e)
        driver.quit()
        print('Error, driver quited')
        pass


def a():
    print(datetime.now())


if __name__ == '__main__':
    # run()
    # exit(0)
    from apscheduler.schedulers.blocking import BlockingScheduler

    sched = BlockingScheduler()
    sched.add_job(run, 'cron', day='*', hour='0', minute='2-15/3,20,30')
    sched.start()
