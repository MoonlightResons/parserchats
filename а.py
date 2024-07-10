import asyncio

from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest, GetHistoryRequest
from telethon.tl.types import InputPeerEmpty, Chat, Channel, PeerUser, PeerChannel

api_id = 18377495
api_hash = 'a0c785ad0fd3e92e7c131f0a70987987'
phone = '996776518608'

async def main(keyword):
    client = TelegramClient(phone, api_id, api_hash)
    await client.start()

    total_messages = 0

    # Get the list of user's chats
    result = await client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=200,
        hash=0
    ))

    # Iterate over all chats
    for dialog in result.chats:
        # Check if the dialog is a group or supergroup (megagroup)
        if isinstance(dialog, (Chat, Channel)):
            try:
                # Get the last 50 messages from each chat
                history = await client(GetHistoryRequest(
                    peer=dialog,
                    limit=50,  # Limit to the last 50 messages
                    offset_date=None,
                    offset_id=0,
                    max_id=0,
                    min_id=0,
                    add_offset=0,
                    hash=0
                ))

                for message in history.messages:
                    if message.message and keyword.lower() in message.message.lower():
                        sender_username = ""
                        chat_title = dialog.title
                        chat_link = f"https://t.me/{dialog.username}" if dialog.username else ""

                        # Check the type of peer
                        if isinstance(message.from_id, PeerUser):
                            from_user = await client.get_entity(message.from_id.user_id)
                            sender_username = f"Sender: @{from_user.username}\n" if from_user.username else "Sender: Unknown\n"
                        elif isinstance(message.from_id, PeerChannel):
                            continue  # Skip messages from channels
                        else:
                            continue  # Skip messages from unknown sources

                        full_message = f"{sender_username}Chat: {chat_title}\n{chat_link}\nMessage: {message.message}"
                        print(full_message)
                        # bot.send_message(chat_id, full_message)
                        total_messages += 1

            except Exception as e:
                print(f"Error processing chat {dialog.title}: {e}")

    print(f"Messages found with keyword '{keyword}': {total_messages}")

    # Send information about the number of found messages
    # if total_messages > 0:
    #     bot.send_message(chat_id, f"Messages found with keyword '{keyword}': {total_messages}")
    # else:
    #     bot.send_message(chat_id, f"No messages found with keyword '{keyword}'.")

    # Disconnect the Telethon client
    await client.disconnect()

keyword = input('Enter the keyword: ')

# Run the main coroutine in the asyncio event loop
asyncio.run(main(keyword))
