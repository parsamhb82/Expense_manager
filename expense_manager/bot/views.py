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


env = environ.Env()
environ.Env.read_env("../expense_manager/.env")
API_KEY = env("API_KEY")
bot = Bot(token=API_KEY)

USERNAME, NAME, DESCRIPTION, MEMBERS = range(4)

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
            room_list = "\n".join([f"{room.name} - /{room.code}" for room in rooms])
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


@csrf_exempt
def telegram_webhook(request):
    payload = json.loads(request.body.decode('UTF-8'))
    update = Update.de_json(payload, bot)
    dispatcher = Dispatcher(bot, update, workers=0)
    dispatcher.add_handler(conversation_handler)
    dispatcher.process_update(update)
    return HttpResponse("Webhook is set!")