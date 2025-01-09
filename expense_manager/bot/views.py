import json
import uuid
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext, ConversationHandler, Updater
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from room.models import Room
from user.models import TelegramUser
import environ
import requests
from .models import RoomCreationSession


env = environ.Env()
environ.Env.read_env("../expense_manager/.env")
API_KEY = env("API_KEY")
url = f"https://api.telegram.org/bot{API_KEY}/sendMessage"
bot = Bot(token=API_KEY)

USERNAME, NAME, DESCRIPTION, MEMBERS, EXPENSE_NAME, EXPENSE_AMOUNT, EXPENSE_PARTICIPANTS = range(7)

def generate_unique_room_code():
    while True:
        room_code = str(uuid.uuid4())[:16].upper()
        if not Room.objects.filter(room_code=room_code).exists():
            return room_code
        
        
def start(update: Update, context: CallbackContext):
    telegram_id = update.effective_user.id
    user, created = TelegramUser.objects.get_or_create(telegram_id=telegram_id)

    if created:
        update.message.reply_text(
            "سلام! لطفاً یک یوزرنیم به انگلیسی وارد کنید:"
        )
        return USERNAME # Return the next state
    else:
        update.message.reply_text(
            f"سلام {user.username}! خوش آمدید."
        )
        return ConversationHandler.END
    
def get_username(update: Update, context: CallbackContext):
    telegram_id = update.effective_user.id
    username = update.message.text.strip()

    if not username.isalnum():
        update.message.reply_text("یوزرنیم فقط باید شامل حروف و اعداد باشد. لطفاً دوباره تلاش کنید.")
        return USERNAME
    
    user = TelegramUser.objects.get(telegram_id=telegram_id)
    user.username = username
    user.save()

    update.message.reply_text(f"یوزرنیم شما با موفقیت تنظیم شد: {username}")
    return ConversationHandler.END 




def cancel(update: Update, context):
    update.message.reply_text("مکالمه لغو شد. برای شروع دوباره /start را وارد کنید.")
    return ConversationHandler.END


def show_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("لیست اتاق‌ها", callback_data='list_rooms')],
        [InlineKeyboardButton("ساخت اتاق جدید", callback_data='create_room')],
        [InlineKeyboardButton("دیدن یوزرنیم", callback_data='show_username')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)

def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == 'list_rooms':
        telegram_id = query.from_user.id
        user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
        if not user:
            query.edit_message_text("ابتدا باید ثبت‌نام کنید با دستور /start")
            return
        
        rooms = user.rooms.all()
        if rooms.exists():
            room_list = "\n".join([f"{room.name}\n{room.description}\n /{room.code}" for room in rooms])
            query.edit_message_text(f"اتاق‌های شما:\n{room_list}")
        else:
            query.edit_message_text("شما در هیچ اتاقی عضو نیستید.")

    elif query.data == 'create_room':
        query.edit_message_text("لطفاً نام اتاق را وارد کنید:")
        return NAME

    elif query.data == 'show_username':
        telegram_id = query.from_user.id
        user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
        if user and user.username:
            query.edit_message_text(f"یوزرنیم شما: {user.username}")
        else:
            query.edit_message_text("شما یوزرنیمی تنظیم نکرده‌اید.")

def create_room_name(update: Update, context: CallbackContext):
    context.user_data['room_name'] = update.message.text
    update.message.reply_text("توضیحات اتاق را وارد کنید:")
    return DESCRIPTION

def create_room_description(update: Update, context: CallbackContext):
    context.user_data['room_description'] = update.message.text
    user_telegram_id = update.effective_user.id
    try:
        user = TelegramUser.objects.get(telegram_id=user_telegram_id)
        room = Room.objects.create(
            name=context.user_data['room_name'],
            description=context.user_data['room_description'],
            admin=user,
            code=generate_unique_room_code()
        )
        room.members.add(user)
        context.user_data["room_id"] = room.id
        update.message.reply_text("یوزرنیم اعضای اتاق را وارد کنید. هر یوزرنیم را در یک پیام بفرستید و برای پایان 0 وارد کنید:")
        return MEMBERS
    except TelegramUser.DoesNotExist:
        update.message.reply_text("شما ابتدا باید ثبت‌نام کنید!")
        return ConversationHandler.END

def create_room_members(update: Update, context: CallbackContext):
    room = Room.objects.get(id=context.user_data["room_id"])
    member = update.message.text
    if member == "0":
        update.message.reply_text(f"اتاق با نام {room.name} ساخته شد!")
        return ConversationHandler.END

    user = TelegramUser.objects.filter(username=member).first()
    if not user:
        update.message.reply_text(f"یوزرنیم {member} یافت نشد. لطفاً دوباره تلاش کنید.")
        return MEMBERS
    room.members.add(user)
    update.message.reply_text(f"یوزرنیم {member} به اتاق اضافه شد.")
    return MEMBERS

conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        USERNAME: [MessageHandler(Filters.text & ~Filters.command, get_username)],
        NAME: [MessageHandler(Filters.text & ~Filters.command, create_room_name)],
        DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, create_room_description)],
        MEMBERS: [MessageHandler(Filters.text & ~Filters.command, create_room_members)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

def send_message(message, CHAT_ID):
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    })
    

def start(CHAT_ID):
    
    user, created = TelegramUser.objects.get_or_create(telegram_id=CHAT_ID)
    
    if user.username:
        message = f"سلام {user.username}! به ربات مدیریت هزینه‌ها خوش آمدید!"
    else:
        message = "سلام به ربات مدیتریت هزینه ها خوش آمدید لطفا یوزرنیم خود را به صورت @username وارد کنید"
    
    send_message(message, CHAT_ID)

def create_username(CHAT_ID, username):
    user, created = TelegramUser.objects.get_or_create(telegram_id=CHAT_ID)
    if created:
        user.username = username
        user.save()
        message = f"یوزرنیم شما با موفقیت ثبت شد. به ربات مدیریت هزینه ها خوش آمدید!"
    else:
        message = "شما قبلا یوزرنیم ثبت کرده اید."
    send_message(message, CHAT_ID)

def send_main_menu(CHAT_ID):
    keyboard = {
        "inline_keyboard": [
            [{"text": "ساخت اتاق جدید", "callback_data": "create_room"}],
            [{"text": "دیدن اتاق هایی که عضو هستم", "callback_data": "view_rooms"}],
            [{"text": "دیدن اتاق های من", "callback_data": "view_my_rooms"}],
        ]
    }
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": "سلام! انتخاب کنید چه کاری می‌خواهید انجام دهید:",
        "reply_markup": keyboard
    })

def start_create_room(CHAT_ID):
    send_message("لطفا نام اتاق را به صورت نام=(نام اتاق) وارد کنید پرانتز هارا نگذارید", CHAT_ID)

@csrf_exempt
def telegram_webhook(request):
    if request.method == 'POST':
        update = Update.de_json(request.body, bot)
        message = update["message"]["text"].strip()
        chat_id = update["message"]["sender_chat"]["id"]
        if message == "/start":
            start(chat_id)
            telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
            if telegram_user.username is not None:
                send_main_menu(chat_id)

        elif message.startswith("@"):
            username = message.split("@")[1]
            create_username(chat_id, username)
            telegram_user = TelegramUser.objects.filter(username=username).first()
            if telegram_user:
                send_main_menu(chat_id)
        
        elif message == "create_room":
            start_create_room(chat_id)
        
        elif message.startswith("نام="):
            room_name = message.split("=")[1].strip()
            telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
            RoomCreationSession.objects.create(user=telegram_user, room_name=room_name)
            send_message("لطفا توضیحات را به شکل توضیحات = توضیحات وارد کنید", chat_id)
        elif message.startswith("توضیحات="):
            room_description = message.split("=")[1].strip()
            session = RoomCreationSession.objects.filter(user__chat_id=chat_id).first()
            if session:
                session.room_description = room_description
                session.save()
                send_message("لطفا یوزرنیم هایی که در اتاق می‌خواهید قرار دهید را به صورت usernames = username1,username2,... وارد کنید", chat_id)
            else :
                send_message("لطفا ابتدا نام اتاق را وارد کنید", chat_id)
                send_main_menu(chat_id)
        elif message.startswith("usernames ="):
            usernames = message[11:].split(",")
            session = RoomCreationSession.objects.filter(user__chat_id=chat_id).first()
            response = ''
            if session:
                room = Room.objects.create(name=session.room_name, description=session.room_description, admin=session.user)
                for username in usernames:
                    user = TelegramUser.objects.filter(username=username.strip()).first()
                    if user:
                        room.members.add(user)
                        response += f"کاربر {user.username} به اتاق اضافه شد\n"
                    else:
                        response += f"کاربر {username} یافت نشد\n"
                room.members.add(session.user)
                send_message(response, chat_id)
                session.delete()
                send_main_menu(chat_id)
            else:
                send_message("لطفا ابتدا نام اتاق و توضیحات را وارد کنید", chat_id)
        


                



        
        


            

        
        return HttpResponse('OK', status=200)
    else:
        return HttpResponse('Invalid request method', status=405)