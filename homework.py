import logging
import os
import sys
import requests
import time
from http import HTTPStatus
from json import JSONDecodeError
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACT_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEG_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

CONFIG_VARS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        message = (f'Сообщение не было отправлено:{error}')
        raise Exception(message) from error
    else:
        logger.info('Сообщение отправлено')


def get_api_answer(current_timestamp):
    """Запрос к API сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = 'Код ответа не равен 200'
            raise Exception(message)
        else:
            logger.info('Запрос прошел успешно')
        return response.json()
    except JSONDecodeError:
        message = 'JSON conversion error'
        raise Exception(message)
    except requests.exceptions.RequestException:
        message = (f'Нет доступа к {ENDPOINT}')
        raise Exception(message)
    except Exception as error:
        message = f'Ошибка API: {error}'
        raise Exception(message)


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных')
    elif response is None:
        raise Exception('Ответ отсутствует')
    else:
        homeworks = response['homeworks']
        if homeworks is None:
            raise ('Нет информации о homeworks')
        elif not isinstance(homeworks, list):
            raise TypeError('Неверный тип данных')
        elif len(homeworks) == 0:
            message = 'Отсутствует ключ homeworks'
            raise IndexError(message)
        else:
            return homeworks


def parse_status(homework):
    """Статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Работы с таким именем не обнаружено')
    if homework['status'] not in HOMEWORK_STATUSES:
        raise KeyError('Непредвиденный статус работы')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка ответа на корректность."""
    for name in CONFIG_VARS:
        if not name:
            logger.critical(f'Отсутствует токен: {name}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.info('Принудительная остановка работы бота')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    updates_none = ''
    message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks != updates_none:
                temp = message
                message = parse_status(homeworks[0])
                if temp != message:
                    send_message(bot, message)
            else:
                logger.debug('Статус домашней работы не обновлен ревьюером')
            current_timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != updates_none:
                send_message(bot, message)
                updates_none = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)

    main()
