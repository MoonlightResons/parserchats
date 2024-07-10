import os
import sqlite3
from telethon import TelegramClient, events, Button
import asyncio
import random

from telethon.tl.functions.messages import GetHistoryRequest, GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, Chat, Channel, PeerUser, PeerChannel, KeyboardButton, ReplyKeyboardMarkup
from telethon.errors import PhoneNumberInvalidError, SessionPasswordNeededError


api_id = 24009406
api_hash = "56b5dee1246cd87bdcd6fcc1049ae95c"
bot_token = '7443055955:AAE7J-qmYmR-1HH8hm6IyhXOd4kWGPs7dcM'

conn = sqlite3.connect('database', check_same_thread=False)
cursor = conn.cursor()

bot = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

tasks = {}


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
    cursor.execute('SELECT id, number FROM accounts WHERE user_id = ?', (user_id,))
    result = cursor.fetchall()
    return result


def get_projects_by_user_id(user_id: int):
    cursor.execute('SELECT id, project_name, account, keyword, off FROM projects WHERE user_id = ?', (user_id,))
    result = cursor.fetchall()
    return [{'id': row[0], 'name': row[1], 'account': row[2], 'keyword': row[3], 'off': row[4]} for row in result]


def get_project_by_id(project_id: int):
    cursor.execute('SELECT project_name, account, keyword, off FROM projects WHERE id = ?', (project_id,))
    result = cursor.fetchone()
    return {'name': result[0], 'account': result[1], 'keyword': result[2], 'off': result[3]}


def delete_project(project_id: int):
    cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
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
def connection_with_user(user_id: int):
    if not get_user_id(user_id):
        cursor.execute('INSERT INTO user_profile (user_id) VALUES (?)', (user_id,))
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


@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    connection_with_user(user_id)

    buttons = [
        [KeyboardButton('Аккаунты'), KeyboardButton('Проекты')]
    ]

    await event.respond('Добро пожаловать!', buttons=buttons)


# Callback handler
@bot.on(events.NewMessage)
async def handle_buttons(event):
    user_id = event.sender_id
    text = event.raw_text

    if text == 'Аккаунты':
        accounts = get_accounts_by_user_id(user_id)

        if len(accounts) == 0:
            await event.respond('У вас нет ни одного аккаунта', buttons=[
                [Button.inline('Добавить аккаунт', b'add_account')]
            ])
        else:
            buttons = [
                [Button.inline(str(account[1]), b'account_' + str(account[0]).encode('utf-8'))] for account in accounts
            ]
            buttons.append([Button.inline('Добавить аккаунт', b'add_account')])
            buttons.append([Button.inline('Назад', b'back_to_main')])
            await event.respond('Ваши аккаунты:', buttons=buttons)

    elif text == 'Проекты':
        projects = get_projects_by_user_id(user_id)

        if len(projects) == 0:
            await event.respond('У вас нет ни одного проекта', buttons=[
                [Button.inline('Добавить проект', b'add_project')]
            ])
        else:
            buttons = [
                [Button.inline(str(project['name']), b'project_' + str(project['id']).encode('utf-8'))] for project in projects
            ]
            buttons.append([Button.inline('Добавить проект', b'add_project')])  # Добавляем кнопку "Добавить проект"
            buttons.append([Button.inline('Назад', b'back_to_main')])
            await event.respond('Ваши проекты:', buttons=buttons)

# Callback handler для inline-кнопок
@bot.on(events.CallbackQuery)
async def callback(event):
    user_id = event.sender_id

    if event.data == b'add_account':
        async with bot.conversation(event.sender_id) as conv:
            await conv.send_message('Введите номер для регистрации')  # Send prompt message first
            phone_number = await conv.get_response()  # Then get response

            await conv.send_message('Отправка кода на указанный номер...')
            await start_login_process(user_id, phone_number.text, conv)

    elif event.data == b'add_project':
        async with bot.conversation(event.sender_id) as conv:
            accounts = get_accounts_by_user_id(user_id)
            if len(accounts) == 0:
                await conv.send_message('У вас нет ни одного аккаунта для привязки проекта.')
                return

            account_buttons = [[Button.inline(str(account[1]), b'select_account_' + str(account[0]).encode('utf-8'))]
                               for account in accounts]
            await conv.send_message('Выберите аккаунт для проекта:', buttons=account_buttons)

            account_response = await conv.wait_event(events.CallbackQuery)
            selected_account = int(account_response.data.decode('utf-8').split('_')[2])

            cursor.execute('SELECT number FROM accounts WHERE id = ?', (selected_account,))
            selected_account_number = cursor.fetchone()[0]

            await conv.send_message('Введите название проекта')
            project_name = await conv.get_response()
            add_project(user_id, selected_account_number, project_name.text, "False")
            await conv.send_message('Проект успешно добавлен')

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

        await event.respond(project_info, buttons=buttons)

    elif event.data.startswith(b'delete_project_'):
        project_id = int(event.data.decode('utf-8').split('_')[2])
        delete_project(project_id)
        await event.respond('Проект удален')

    elif event.data.startswith(b'toggle_project_'):
        project_id = int(event.data.decode('utf-8').split('_')[2])
        project = get_project_by_id(project_id)
        get_state = toggle_project_get_state(project_id)
        if project['keyword'] is None:
            await event.respond('Для того что бы включить парсер добавьте ключевое слово')
        else:
            if get_state == "False":
                toggle_project(project_id, "True")
                await event.respond('Вы успешно запустили парсер')
                # await message_parser(event, project_id)
                task = bot.loop.create_task(periodic_parser(event, project_id))
                tasks[project_id] = task
            else:
                toggle_project(project_id, "False")
                await event.respond('Вы успешно выключили парсер')
                if project_id in tasks:
                    tasks[project_id].cancel()
                    del tasks[project_id]
                phone = get_project_by_id(project_id)['account']
                file_path = f"{phone}.txt"
                if os.path.exists(file_path):
                    os.remove(file_path)
                await event.respond('Состояние проекта изменено')

    elif event.data.startswith(b'keyword_project_'):
        project_id = int(event.data.decode('utf-8').split('_')[2])
        async with bot.conversation(event.sender_id) as conv:
            await conv.send_message('Введите новое ключевое слово')
            keyword = await conv.get_response()
            update_project_keyword(project_id, keyword.text)
            await conv.send_message('Ключевое слово обновлено')

    elif event.data == b'cancel_proj':
        projects = get_projects_by_user_id(user_id)

        if len(projects) == 0:
            await event.respond('У вас нет ни одного проекта', buttons=[
                [Button.inline('Добавить проект', b'add_project')]
            ])
        else:
            buttons = [
                [Button.inline(str(project['name']), b'project_' + str(project['id']).encode('utf-8'))] for project in projects
            ]
            buttons.append([Button.inline('Добавить проект', b'add_project')])  # Добавляем кнопку "Добавить проект"
            buttons.append([Button.inline('Назад', b'back_to_main')])
            await event.respond('Ваши проекты:', buttons=buttons)


async def start_login_process(user_id, phone_number, conv):
    session_name = f"{phone_number}.session"
    client = TelegramClient(session_name, api_id, api_hash)
    await client.connect()

    try:
        if not await client.is_user_authorized():
            await client.send_code_request(phone_number)
            await conv.send_message('Введите код из сообщения')
            code = await conv.get_response()
            await complete_login(user_id, client, phone_number, code.text, conv)
    except PhoneNumberInvalidError:
        await conv.send_message('Код подтверждения устарел. Пожалуйста, запросите новый код и попробуйте снова.')
    except SessionPasswordNeededError:
        await conv.send_message('Отключите двухфакторную аутентификацию и попробуйте снова.')
    except Exception as e:
        await conv.send_message(f'Ошибка при добавлении аккаунта: {str(e)}')
    finally:
        await client.disconnect()


async def complete_login(user_id, client, phone_number, code, conv):
    try:
        await client.sign_in(phone_number, code)
        session_str = client.session.save()  # Сохранение сессии
        random_session = session_generate()
        add_account(user_id, phone_number, "True", random_session)
        account_update(random_session, "True")
        await conv.send_message('Аккаунт успешно добавлен', buttons=start_button())
    except PhoneNumberInvalidError:
        await conv.send_message('Код подтверждения неверен. Пожалуйста, попробуйте снова.')
    except SessionPasswordNeededError:
        await conv.send_message('Отключите двухфакторную аутентификацию и попробуйте снова.')
    except Exception as e:
        await conv.send_message(f'Ошибка при добавлении аккаунта: {str(e)}')

def main():
    bot.run_until_disconnected()


if __name__ == '__main__':
    main()
