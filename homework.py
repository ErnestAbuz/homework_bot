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

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    filename='logger.log')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


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
    """Отправка сообщения в Telegram"""
    try:
        logger.info('Сообщение отправлено')
        return bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'Сообщение не было отправлено:{error}')


def get_api_answer(current_timestamp):
    """Запрос к API сервиса"""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = 'Код ответа не равен 200'
            logger.error(message)
            raise Exception(message)
        return response.json()
    except requests.exceptions.RequestException:
        message = (f'Нет доступа к {ENDPOINT}')
        logger.error(message)
        raise Exception(message)
    except JSONDecodeError:
        message = 'JSON conversion error'
        logger.error(message)
        raise Exception(message)
    except Exception as error:
        message = f'Ошибка API: {error}'
        logger.error(message)
        raise Exception(message)
    finally:
        logger.info('Запрос прошел успешно')


def check_response(response):
    """Проверка ответа API"""
    if not isinstance(response, dict):
        logger.error('Неверный тип данных')
        raise TypeError('Неверный тип данных')
    if response is None:
        raise Exception('Ответ отсутствует')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error('Неверный тип данных')
        raise TypeError('Неверный тип данных')
    if len(homeworks) != 0:
        return homeworks
    message = 'Отсутствует ключ homeworks'
    raise IndexError(message)


def parse_status(homework):
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if 'homework_name' not in homework:
        logger.error('Работы с таким именем не обнаружено')
        raise KeyError('Работы с таким именем не обнаружено')
    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Непредвиденный статус работы')
        raise KeyError('Непредвиденный статус работы')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    for name in CONFIG_VARS:
        token = globals()[name]
        if not token:
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
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks != updates_none:
                message = parse_status(homeworks[0])
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
    main()
