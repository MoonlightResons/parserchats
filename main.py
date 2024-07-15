import json
import os
import sqlite3
import time

import telebot
from telethon import TelegramClient, events, Button
import asyncio
import random

from telethon.tl.functions.messages import GetHistoryRequest, GetDialogsRequest, DeleteMessagesRequest
from telethon.tl.types import InputPeerEmpty, Chat, Channel, PeerUser, PeerChannel, KeyboardButton, ReplyKeyboardMarkup, \
    KeyboardButtonRow
from telethon.errors import PhoneNumberInvalidError, SessionPasswordNeededError, MessageDeleteForbiddenError, \
    PhoneCodeExpiredError, PhoneCodeInvalidError

api_id = 29302356
api_hash = "7d7f24983b3bea974a0997c5c42a1d44"
bot_token = '7443055955:AAE7J-qmYmR-1HH8hm6IyhXOd4kWGPs7dcM'

conn = sqlite3.connect('database', check_same_thread=False)
cursor = conn.cursor()

bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)
bot_tb = telebot.TeleBot(token=bot_token)

tasks = {}


async def delete_messages(user_id, message_ids):
    for message_id in message_ids:
        try:
            await bot.delete_messages(user_id, message_id)
        except MessageDeleteForbiddenError:
            print(f"Cannot delete message {message_id}: Forbidden")
        except Exception as e:
            print(f"Error deleting message {message_id}: {e}")


def start_button():
    buttons = [
        [Button.inline('Аккаунты', b'accounts'), Button.inline('Проекты', b'projects')]
    ]

    return buttons


def session_generate():
    session = random.randint(1, 10000000)
    return session


def get_user_id(user_id: int) -> bool:
    cursor.execute('SELECT 1 FROM user_profile WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None


# Function to get accounts by user_id
def get_accounts_by_user_id(user_id: int):
    query = "SELECT id, number FROM accounts WHERE user_id = ? AND confirm = ?"
    cursor.execute(query, (user_id, "True"))
    result = cursor.fetchall()
    return [{'id': row[0], 'name': row[1]} for row in result]


def get_confirm_by_user_id(user_id):
    # Assuming you have a database connection established
    query = "SELECT * FROM accounts WHERE user_id = ? AND confirm = ?"
    cursor.execute(query, (user_id, "True"))
    accounts = cursor.fetchall()
    return accounts


def get_projects_by_user_id(user_id: int):
    cursor.execute('SELECT id, project_name, account, keyword, off FROM projects WHERE user_id = ?', (user_id,))
    result = cursor.fetchall()
    return [{'id': row[0], 'name': row[1], 'account': row[2], 'keyword': row[3], 'off': row[4]} for row in result]


def get_project_by_id(project_id: int):
    cursor.execute('SELECT project_name, account, keyword, off FROM projects WHERE id = ?', (project_id,))
    result = cursor.fetchone()
    return {'name': result[0], 'account': result[1], 'keyword': result[2], 'off': result[3]}


def get_account_by_id(account_id: int):
    cursor.execute('SELECT number FROM accounts WHERE id = ?', (account_id,))
    result = cursor.fetchone()
    return {'name': result[0]}


def delete_project(project_id: int):
    cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    conn.commit()


def delete_account(account_id: int):
    cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
    conn.commit()


def toggle_project(project_id: int, off: str):
    cursor.execute('UPDATE projects SET off = ? WHERE id = ?', (off, project_id))
    conn.commit()


def toggle_project_get_state(project_id: int):
    cursor.execute('SELECT off FROM projects WHERE id = ?', (project_id,))
    current_state = cursor.fetchone()[0]
    return current_state


def update_project_keyword(project_id: int, keyword: str):
    cursor.execute('UPDATE projects SET keyword = ? WHERE id = ?', (keyword, project_id))
    conn.commit()


# Function to add a new user
def connection_with_user(user_id: int, message_ids: list):
    if not get_user_id(user_id):
        cursor.execute('INSERT INTO user_profile (user_id, message_ids) VALUES (?, ?)', (user_id, json.dumps(message_ids)))
        conn.commit()
        print(f"User {user_id} added to database.")
    else:
        print(f"User {user_id} already exists in database.")


# Function to add an account
def add_account(user_id: int, number: str, confirm: str, session: int):
    cursor.execute('INSERT INTO accounts (user_id, number, confirm, session) VALUES (?, ?, ?, ?)', (user_id, number,
                                                                                                    confirm, session,))
    conn.commit()


def account_update(confirm: str, session: int):
    cursor.execute("UPDATE accounts SET confirm = ? WHERE session = ?", (confirm, session))
    conn.commit()


def add_project(user_id: int, account: int, project_name: str, off: str):
    cursor.execute('INSERT INTO projects (user_id, account, project_name, off) VALUES (?, ?, ?, ?)', (user_id, account, project_name, off,))
    conn.commit()


def update_message_id(user_id: int, message_id: int):
    cursor.execute('SELECT message_ids FROM user_profile WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result and isinstance(result[0], str):
        try:
            message_ids = json.loads(result[0])  # Convert the stored string back to a list
        except json.JSONDecodeError:
            message_ids = []
    else:
        message_ids = []

    message_ids.append(message_id)  # Add the new message_id to the list
    cursor.execute('UPDATE user_profile SET message_ids = ? WHERE user_id = ?',
                   (json.dumps(message_ids), user_id))  # Convert the list back to a string
    conn.commit()


def clear_all_message_ids(user_id: int):
    cursor.execute("SELECT message_ids FROM user_profile WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        message_ids = json.loads(result[0])
        # Clear the message_ids list
        message_ids.clear()
        # Update the database with the cleared list
        cursor.execute("UPDATE user_profile SET message_ids = ? WHERE user_id = ?", (json.dumps(message_ids), user_id))
        conn.commit()


def get_message_from_profile(user_id: int):
    cursor.execute("SELECT message_ids FROM user_profile WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return json.loads(result[0])  # Convert the stored JSON string back to a list
    return []


async def project_get_button(event, project_id, project):
    user_id = event.sender_id
    project_info = (f"Название проекта: {project['name']}\n"
                    f"Привязанный номер: {project['account']}\n"
                    f"Ключевое слово: {'Нету' if project['keyword'] is None else project['keyword']}")

    buttons = [
        [Button.inline('Удалить', b'delete_project_' + str(project_id).encode('utf-8'))],
        [Button.inline('Выкл' if project['off'] == "False" else 'Вкл',
                       b'toggle_project_' + str(project_id).encode('utf-8'))],
        [Button.inline('Ключевое слово', b'keyword_project_' + str(project_id).encode('utf-8'))],
        [Button.inline('Назад', b'cancel_proj')]
    ]

    message = await event.respond(project_info, buttons=buttons)
    update_message_id(user_id, message.id)


async def message_parser(event, project_id):
    project = get_project_by_id(project_id)
    keyword = project['keyword']
    phone = project['account']
    client = TelegramClient(str(phone), api_id, api_hash)
    await client.start()

    total_messages = 0
    processed_message_ids = set()

    # Читаем существующие ID сообщений из файла
    try:
        with open(f"{phone}.txt", "r") as file:
            processed_message_ids = set(file.read().splitlines())
    except FileNotFoundError:
        pass

    async def send_message(message, dialog):
        sender_username = ""
        chat_title = dialog.title
        chat_link = f"https://t.me/{dialog.username}" if dialog.username else ""

        if isinstance(message.from_id, PeerUser):
            from_user = await client.get_entity(message.from_id.user_id)
            sender_username = f"Отправитель: @{from_user.username}\n" if from_user.username else "Отправитель: Неизвестно\n"
        elif isinstance(message.from_id, PeerChannel):
            return  # Пропускаем сообщения от каналов
        else:
            return  # Пропускаем сообщения от неизвестных источников

        full_message = f"{sender_username}Чат: {chat_title}\n{chat_link}\nСообщение: {message.message}"
        await event.respond(full_message)

    async def parse_messages():
        nonlocal total_messages
        try:
            dialogs = await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))

            for dialog in dialogs.chats:
                if isinstance(dialog, (Chat, Channel)):
                    history = await client(GetHistoryRequest(
                        peer=dialog,
                        limit=50,
                        offset_date=None,
                        offset_id=0,
                        max_id=0,
                        min_id=0,
                        add_offset=0,
                        hash=0
                    ))

                    for message in history.messages:
                        if message.message and keyword.lower() in message.message.lower():
                            # Пропускаем сообщения, которые уже были обработаны
                            if str(message.id) in processed_message_ids:
                                continue
                            await send_message(message, dialog)
                            total_messages += 1
                            processed_message_ids.add(str(message.id))

        except Exception as e:
            print(f"Ошибка при обработке сообщений: {e}")

        print(f"Найдено сообщений с ключевым словом '{keyword}': {total_messages}")

        # Записываем новые ID сообщений в файл
        with open(f"{phone}.txt", "w") as file:
            for message_id in processed_message_ids:
                file.write(f"{message_id}\n")

    await parse_messages()
    await client.disconnect()


async def periodic_parser(event, project_id):
    while True:
        await message_parser(event, project_id)
        await asyncio.sleep(60)  # Запускать парсинг каждые 1 минуту


def start_buttons():
    keyboard_buttons = ReplyKeyboardMarkup(
        [
            KeyboardButtonRow(
                [
                    KeyboardButton(text='Аккаунты'),
                    KeyboardButton(text="Проекты")
                ]
            )
        ],
        resize=True
    )

    return keyboard_buttons


async def accounts_button(user_id, conv):
    accounts = get_accounts_by_user_id(user_id)

    if len(accounts) == 0:
        message1 = await conv.send_message('У вас нет ни одного аккаунта', buttons=[
            [Button.inline('Добавить аккаунт', b'add_account')]
        ])
        update_message_id(user_id, message1.id)
    else:
        buttons = [
            [Button.inline(str(account['name']), b'account_' + str(account['id']).encode('utf-8'))] for account in accounts
        ]
        buttons.append([Button.inline('Добавить аккаунт', b'add_account')])

        message2 = await conv.send_message('Ваши аккаунты:', buttons=buttons)
        update_message_id(user_id, message2.id)


async def accounts_button_event(user_id, event):
    accounts = get_accounts_by_user_id(user_id)

    if len(accounts) == 0:
        message1 = await event.respond('У вас нет ни одного аккаунта', buttons=[
            [Button.inline('Добавить аккаунт', b'add_account')]
        ])
        update_message_id(user_id, message1.id)
    else:
        buttons = [
            [Button.inline(str(account['name']), b'account_' + str(account['id']).encode('utf-8'))] for account in accounts
        ]
        buttons.append([Button.inline('Добавить аккаунт', b'add_account')])

        message2 = await event.respond('Ваши аккаунты:', buttons=buttons)
        update_message_id(user_id, message2.id)


async def projects_button(user_id, conv):
    projects = get_projects_by_user_id(user_id)

    if len(projects) == 0:
        message1 = await conv.send_message('У вас нет ни одного проекта', buttons=[
            [Button.inline('Добавить проект', b'add_project')]
        ])
        update_message_id(user_id, message1.id)
    else:
        buttons = [
            [Button.inline(str(project['name']), b'project_' + str(project['id']).encode('utf-8'))] for project in
            projects
        ]
        buttons.append([Button.inline('Добавить проект', b'add_project')])

        message2 = await conv.send_message('Ваши аккаунты:', buttons=buttons)
        update_message_id(user_id, message2.id)


async def projects_button_event(user_id, event):
    projects = get_projects_by_user_id(user_id)

    if len(projects) == 0:
        message1 = await event.respond('У вас нет ни одного проекта', buttons=[
            [Button.inline('Добавить проект', b'add_project')]
        ])
        update_message_id(user_id, message1.id)
    else:
        buttons = [
            [Button.inline(str(project['name']), b'project_' + str(project['id']).encode('utf-8'))] for project in
            projects
        ]
        buttons.append([Button.inline('Добавить проект', b'add_project')])

        message2 = await event.respond('Ваши аккаунты:', buttons=buttons)
        update_message_id(user_id, message2.id)


@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    # all_messages = get_message_from_profile(user_id)
    # await delete_messages(user_id, all_messages)
    # clear_all_message_ids(user_id)
    connection_with_user(user_id, [])

    await event.respond('Добро пожаловать!', buttons=start_buttons())
    # update_message_id(user_id, message.id)


@bot.on(events.NewMessage)
async def handle_buttons(event):
    user_id = event.sender_id
    text = event.raw_text
    accounts = get_accounts_by_user_id(user_id)

    if text == 'Аккаунты':
        if len(accounts) == 0:
            message1 = await event.respond('У вас нет ни одного аккаунта', buttons=[
                [Button.inline('Добавить аккаунт', b'add_account')]
            ])
            update_message_id(user_id, message1.id)
        else:
            buttons = [
                [Button.inline(str(account['name']), b'account_' + str(account['id']).encode('utf-8'))] for account in
                accounts
            ]
            buttons.append([Button.inline('Добавить аккаунт', b'add_account')])

            message2 = await event.respond('Ваши аккаунты:', buttons=buttons)
            update_message_id(user_id, message2.id)

    elif text == 'Проекты':
        all_messages = get_message_from_profile(user_id)
        projects = get_projects_by_user_id(user_id)
        await delete_messages(user_id, all_messages)
        clear_all_message_ids(user_id)

        if len(projects) == 0:
            message1 = await event.respond('У вас нет ни одного проекта', buttons=[
                [Button.inline('Добавить проект', b'add_project')]
            ])
            update_message_id(user_id, message1.id)
        else:
            buttons = [
                [Button.inline(str(project['name']), b'project_' + str(project['id']).encode('utf-8'))] for project in projects
            ]
            buttons.append([Button.inline('Добавить проект', b'add_project')])  # Добавляем кнопку "Добавить проект"
            message = await event.respond('Ваши проекты:', buttons=buttons)
            update_message_id(user_id, message.id)


@bot.on(events.CallbackQuery)
async def callback(event):
    user_id = event.sender_id

    if event.data == b'add_account':
        async with bot.conversation(event.sender_id) as conv:
            message1 = await conv.send_message('Введите номер для регистрации')
            update_message_id(user_id, message1.id)
            phone_number = await conv.get_response()  # Then get response

            message2 = await conv.send_message('Отправка кода на указанный номер...')
            update_message_id(user_id, message2.id)
            await start_login_process(user_id, phone_number.text, conv)

    elif event.data.startswith(b'account_'):
        account_id = int(event.data.decode('utf-8').split('_')[1])
        account = get_account_by_id(account_id)

        account_info = (f'Номер: {account["name"]}')

        buttons = [
            [Button.inline('Удалить', b'delete_account_' + str(account_id).encode('utf-8'))],
        ]

        message = await event.respond(account_info, buttons=buttons)
        update_message_id(user_id, message.id)

    elif event.data == b'add_project':
        async with bot.conversation(event.sender_id) as conv:
            accounts = get_accounts_by_user_id(user_id)
            if len(accounts) == 0:
                message = await conv.send_message('У вас нет ни одного аккаунта для привязки проекта.')
                update_message_id(user_id, message.id)
                return

            account_buttons = [[Button.inline(str(account['name']), b'select_account_' + str(account['id']).encode('utf-8'))]
                               for account in accounts]
            message1 = await conv.send_message('Выберите аккаунт для проекта:', buttons=account_buttons)
            update_message_id(user_id, message1.id)

            account_response = await conv.wait_event(events.CallbackQuery)
            selected_account = int(account_response.data.decode('utf-8').split('_')[2])

            cursor.execute('SELECT number FROM accounts WHERE id = ?', (selected_account,))
            selected_account_number = cursor.fetchone()[0]

            message2 = await conv.send_message('Введите название проекта')
            update_message_id(user_id, message2.id)
            project_name = await conv.get_response()
            add_project(user_id, selected_account_number, project_name.text, "False")
            all_messages = get_message_from_profile(user_id)
            message4 = await conv.send_message('Проект успешно добавлен')
            await projects_button(user_id, conv)
            await delete_messages(user_id, all_messages)
            update_message_id(user_id, message4 .id)

    elif event.data.startswith(b'project_'):
        project_id = int(event.data.decode('utf-8').split('_')[1])
        project = get_project_by_id(project_id)

        project_info = (f"Название проекта: {project['name']}\n"
                        f"Привязанный номер: {project['account']}\n"
                        f"Ключевое слово: {'Нету' if project['keyword'] is None else project['keyword']}")

        buttons = [
            [Button.inline('Удалить', b'delete_project_' + str(project_id).encode('utf-8'))],
            [Button.inline('Выкл' if project['off'] == "True" else 'Вкл',
                           b'toggle_project_' + str(project_id).encode('utf-8'))],
            [Button.inline('Ключевое слово', b'keyword_project_' + str(project_id).encode('utf-8'))],
            [Button.inline('Назад', b'cancel_proj')]
        ]

        message = await event.respond(project_info, buttons=buttons)
        update_message_id(user_id, message.id)

    elif event.data.startswith(b'delete_project_'):
        project_id = int(event.data.decode('utf-8').split('_')[2])
        delete_project(project_id)
        all_messages = get_message_from_profile(user_id)
        message = await event.respond('Проект удален')
        await delete_messages(user_id, all_messages)
        clear_all_message_ids(user_id)
        update_message_id(user_id, message.id)
        await projects_button_event(user_id, event)

    elif event.data.startswith(b'delete_account_'):
        account_id = int(event.data.decode('utf-8').split('_')[2])
        account = get_account_by_id(account_id)
        phone = account['name']
        session_name = f'{phone}.session'
        delete_account(account_id)
        message = await event.respond('Аккаунт удален')
        all_messages = get_message_from_profile(user_id)
        await delete_messages(user_id, all_messages)
        clear_all_message_ids(user_id)
        update_message_id(user_id, message.id)
        await accounts_button_event(user_id, event)
        if os.path.exists(session_name):
            os.remove(session_name)

    elif event.data.startswith(b'toggle_project_'):
        project_id = int(event.data.decode('utf-8').split('_')[2])
        project = get_project_by_id(project_id)
        get_state = toggle_project_get_state(project_id)
        if project['keyword'] is None:
            message = await event.respond('Для того что бы включить парсер добавьте ключевое слово')
            update_message_id(user_id, message.id)
        else:
            if get_state == "False":
                toggle_project(project_id, "True")
                message1 = await event.respond('Вы успешно запустили парсер')
                update_message_id(user_id, message1.id)
                all_messages = get_message_from_profile(user_id)
                await delete_messages(user_id, all_messages)
                task = bot.loop.create_task(periodic_parser(event, project_id))
                tasks[project_id] = task
                await project_get_button(event=event, project_id=project_id, project=project)
            else:
                toggle_project(project_id, "False")
                message2 = await event.respond('Вы успешно выключили парсер')
                update_message_id(user_id, message2.id)
                all_messages = get_message_from_profile(user_id)
                await delete_messages(user_id, all_messages)
                clear_all_message_ids(user_id)
                await project_get_button(event=event, project_id=project_id, project=project)
                if project_id in tasks:
                    tasks[project_id].cancel()
                    del tasks[project_id]
                phone = get_project_by_id(project_id)['account']
                file_path = f"{phone}.txt"
                if os.path.exists(file_path):
                    os.remove(file_path)
                message3 = await event.respond('Состояние проекта изменено')
                update_message_id(user_id, message3.id)

    elif event.data.startswith(b'keyword_project_'):
        user_id = event.sender_id
        project_id = int(event.data.decode('utf-8').split('_')[2])

        async with bot.conversation(event.sender_id) as conv:
            message1 = await conv.send_message('Введите новое ключевое слово')
            keyword = await conv.get_response()
            update_message_id(user_id, message1.id)
            update_project_keyword(project_id, keyword.text)
            message2 = await conv.send_message('Ключевое слово обновлено')
            all_messages = get_message_from_profile(user_id)
            await delete_messages(user_id, all_messages)
            clear_all_message_ids(user_id)
            await projects_button(user_id, conv)
            update_message_id(user_id, message2.id)

    elif event.data == b'cancel_proj':
        all_messages = get_message_from_profile(user_id)
        await delete_messages(user_id, all_messages)
        await projects_button_event(user_id, event)

async def start_login_process(user_id, phone_number, conv):
    session_name = f"{phone_number}.session"
    if os.path.exists(session_name):
        os.remove(session_name)
    client = TelegramClient(session_name, api_id, api_hash)
    await client.connect()

    login_successful = False  # Flag to indicate if login was successful

    try:
        if not await client.is_user_authorized():
            await client.send_code_request(phone_number)
            message = await conv.send_message('Введите код из сообщения')
            update_message_id(user_id, message.id)
            code = await conv.get_response()
            login_successful = await complete_login(user_id, client, phone_number, code.text, conv)
    except PhoneNumberInvalidError:
        message1 = await conv.send_message('Код подтверждения устарел. Пожалуйста, запросите новый код и попробуйте снова.')
        update_message_id(user_id, message1.id)
    except SessionPasswordNeededError:
        message2 = await conv.send_message('Отключите двухфакторную аутентификацию и попробуйте снова.')
        update_message_id(user_id, message2.id)
    except PhoneCodeExpiredError:
        message4 = await conv.send_message('Устройство с помощью которого вы пытаетесь войти по номеру телефона '
                                           'является временно индексированным конкретно для этого номера '
                                           'попробуйте позже или воспользуйтесь другим устройством')
        update_message_id(user_id, message4.id)
    except Exception as e:
        message3 = await conv.send_message(f'Ошибка при добавлении аккаунта: {str(e)}')
        update_message_id(user_id, message3.id)
    finally:
        await disconnect_and_cleanup(client, session_name, login_successful)

async def complete_login(user_id, client, phone_number, code, conv):
    session_name = f"{phone_number}.session"
    try:
        await client.sign_in(phone_number, code)
        session_str = client.session.save()  # Сохранение сессии
        random_session = session_generate()
        add_account(user_id, phone_number, "False", random_session)
        account_update("True", random_session)
        message = await conv.send_message('Аккаунт успешно добавлен')
        all_messages = get_message_from_profile(user_id)
        await delete_messages(user_id, all_messages)
        update_message_id(user_id, message.id)
        await accounts_button(user_id, conv)  # Await the coroutine here
        return True  # Indicate successful login
    except PhoneNumberInvalidError:
        message1 = await conv.send_message('Код подтверждения неверен. Пожалуйста, попробуйте снова.')
        all_messages = get_message_from_profile(user_id)
        await delete_messages(user_id, all_messages)
        update_message_id(user_id, message1.id)
    except PhoneCodeExpiredError:
        message4 = await conv.send_message('Устройство с помощью которого вы пытаетесь войти по номеру телефона '
                                           'является временно индексированным конкретно для этого номера '
                                           'попробуйте позже или воспользуйтесь другим устройством')
        update_message_id(user_id, message4.id)
    except SessionPasswordNeededError:
        message2 = await conv.send_message('Отключите двухфакторную аутентификацию и попробуйте снова.')
        all_messages = get_message_from_profile(user_id)
        await delete_messages(user_id, all_messages)
        update_message_id(user_id, message2.id)
    except Exception as e:
        message3 = await conv.send_message(f'Ошибка при добавлении аккаунта: {str(e)}')
        all_messages = get_message_from_profile(user_id)
        await delete_messages(user_id, all_messages)
        update_message_id(user_id, message3.id)
    return False  # Indicate unsuccessful login

async def disconnect_and_cleanup(client, session_name, login_successful):
    await client.disconnect()
    # Wait to ensure the file is closed
    time.sleep(1)
    # Only delete the session file if login was unsuccessful
    if not login_successful:
        # Retry deleting the session file if necessary
        for _ in range(5):
            try:
                if os.path.exists(session_name):
                    os.remove(session_name)
                break
            except PermissionError:
                time.sleep(1)

def main():
    bot.run_until_disconnected()


if __name__ == '__main__':
    main()
