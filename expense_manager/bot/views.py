import json
import uuid
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext, ConversationHandler, Updater
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from room.models import Room, Expense, Payment
from user.models import TelegramUser
import environ
import requests
from .models import RoomCreationSession, ExpenseCreationSession, AddRoomMemberSession


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

def send_message_with_keyboard(message, keyboard, CHAT_ID):
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message,
        "reply_markup": json.dumps({"keyboard": keyboard})
    })
room_creation_cancle_keyboard = [
    [InlineKeyboardButton("لغو", callback_data='cancel_room_creation')]
]

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
    send_message_with_keyboard("لطفا نام اتاق را به صورت نام=(نام اتاق) وارد کنید پرانتز هارا نگذارید",room_creation_cancle_keyboard, CHAT_ID)

def send_room_main_menu(CHAT_ID, room):
    keyboard = {
        "inline_keyboard": [
            [{"text": "دیدن اعضای اتاق", "callback_data": f"view_room_members={room.id}"}],
            [{"text": "دیدن بدهکاری های من", "callback_data": f"view_my_debts={room.id}"}],
            [{"text": "دیدن بستانکاری های من", "callback_data": f"view_my_credits={room.id}"}]
            [{"text": "افزودن هزینه جدید", "callback_data": f"add_expense={room.id}"}],
            [{"text": "اضافه کردن اعضا", "callback_data": f"add_room_members={room.id}"}],
            [{"text": "بازگشت به منوی اصلی", "callback_data": "main_menu"}],
        ]
    }
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": f"منوی اتاق {room.name}",
        "reply_markup": keyboard
    })

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
        
        elif message == "cancel_room_creation":
            session = RoomCreationSession.objects.filter(user__chat_id=chat_id)
            if session:
                session.delete()
                send_message("از ساخت اتاق کنسل شد.", chat_id)
            else:
                send_message("اتاقی وجود نداشت برای کنسل کردن", chat_id)
            
            send_main_menu(chat_id)

        
        elif message.startswith("نام="):
            room_name = message.split("=")[1].strip()
            telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
            RoomCreationSession.objects.create(user=telegram_user, room_name=room_name)
            send_message_with_keyboard("لطفا توضیحات را به شکل توضیحات = توضیحات وارد کنید", room_creation_cancle_keyboard, chat_id)


        elif message.startswith("توضیحات="):
            room_description = message.split("=")[1].strip()
            session = RoomCreationSession.objects.filter(user__chat_id=chat_id).first()
            if session:
                session.room_description = room_description
                session.save()
                send_message_with_keyboard("لطفا یوزرنیم هایی که در اتاق می‌خواهید قرار دهید را به صورت usernames = username1,username2,... وارد کنید", room_creation_cancle_keyboard,chat_id)
            else :
                send_message("لطفا ابتدا نام اتاق را وارد کنید", chat_id)
                send_main_menu(chat_id)
        elif message.startswith("usernames ="):
            usernames = message[11:].split(",")
            session = RoomCreationSession.objects.filter(user__chat_id=chat_id).first()
            response = ''
            if session:
                room = Room.objects.create(name=session.room_name, description=session.room_description, admin=session.user, code = generate_unique_room_code())
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
        
        elif message == "show_username":
            telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
            if telegram_user:
                send_message(f"یوزرنیم شما: {telegram_user.username}", chat_id)
                send_main_menu(chat_id)
            else:
                send_message("شما یوزرنیمی ندارید. لطفا ابتدا یوزرنیم خود را ثبت کنید.", chat_id)
        
        elif message == "list_rooms":
            telegram_user = TelegramUser.objects.get(chat_id=chat_id)
            rooms = telegram_user.rooms.all()
            if rooms:
                response = "اتاق های شما:\n"
                for room in rooms:
                    response += f"{room.name}\n{room.description}\ncode = /{room.code}\n"
                send_message(response, chat_id)
                send_main_menu(chat_id)
            else:
                send_message("شما در هیچ اتاقی عضو نیستید.", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("/") and message != "/start":
            code = message[1:]
            room = Room.objects.filter(code=code).first()
            if room:
                telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
                if telegram_user:
                    if telegram_user in room.members.all():
                        send_room_main_menu(chat_id, room)
                    else:
                        send_message("شما در این اتاق عضو نیستید.", chat_id)
                        send_main_menu(chat_id)
                else:
                    send_message("شما یوزرنیمی ندارید. لطفا ابتدا یوزرنیم خود را ثبت کنید.", chat_id)
                    send_main_menu(chat_id)
            else:
                send_message("اتاق یافت نشد.", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("view_room_members"):
            room_id = int(message.split("=")[1].strip())
            room = Room.objects.filter(id=room_id).first()
            if room:
                members = room.members.all()
                response = "اعضای اتاق:\n"
                for member in members:
                    response += f"{member.username}\n"
                send_message(response, chat_id)
                send_room_main_menu(chat_id, room)
            else:
                send_message("اتاق یافت نشد.", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("add_expense"):
            room_id = int(message.split("=")[1].strip())
            room = Room.objects.filter(id=room_id).first()
            if room:
                telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
                expense_creation_session_bef = ExpenseCreationSession.objects.filter(payer=telegram_user).first()
                if expense_creation_session_bef:
                    expense_creation_session_bef.delete()
                if telegram_user:
                    if telegram_user in room.members.all():
                        expense_creation_session = ExpenseCreationSession.objects.create(room=room, payer=telegram_user)
                        send_message("لطفا نام هزینه را به صورت نام هزینه = نام وارد کنید ", chat_id)
                    else:
                        send_message("شما در این اتاق عضو نیستید.", chat_id)
                        send_main_menu(chat_id)
                else:
                    send_message("شما یوزرنیمی ندارید. لطفا ابتدا یوزرنیم خود را ثبت کنید.", chat_id)
                    send_main_menu(chat_id)
            
        elif message.startswith("نام هزینه"):
            expense_creation_session = ExpenseCreationSession.objects.filter(user__chat_id=chat_id).first()
            if expense_creation_session:
                expense_name = message.split("=")[1].strip()
                expense_creation_session.name = expense_name
                expense_creation_session.save()
                send_message("لطفا مبلغ هزینه را به صورت مبلغ هزینه = مبلغ وارد کنید", chat_id)
            else:
                send_message("لطفا ابتدا یک اتاق را انتخاب کنید", chat_id)
                send_main_menu(chat_id)

        elif message.startswith("مبلغ هزینه"):
            expense_creation_session = ExpenseCreationSession.objects.filter(user__chat_id=chat_id).first()
            if expense_creation_session:
                expense_amount = int(message.split("=")[1].strip())
                expense_creation_session.amount = expense_amount
                expense_creation_session.save()
                send_message("لطفا توضیحات هزینه را به صورت توضیحات هزینه = توضیحات وارد کنید", chat_id)
            elif expense_creation_session and not expense_creation_session.expense_name:
                send_message("لطفا از ابتدا شروع کن و برای هزینه اسم انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            else:
                send_message("لطفا ابتدا یک اتاق را انتخاب کنید", chat_id)
                send_main_menu(chat_id)
        elif message.startswith("توضیحات هزینه"):
            expense_creation_session = ExpenseCreationSession.objects.filter(user__chat_id=chat_id).first()
            if expense_creation_session:
                expense_description = message.split("=")[1].strip()
                expense_creation_session.description = expense_description
                expense_creation_session.save()
                send_message(" حالا یوزرنیم افرادی که میخواهی ثبت کنی را به شکل eusernames = username1, username2, ... وارد کن", chat_id)
            elif expense_creation_session and not expense_creation_session.expense_name:
                send_message("لطفا از ابتدا شروع کن و برای هزینه اسم انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            elif expense_creation_session and not expense_creation_session.expense_amount:
                send_message("لطفا از ابتدا شروع کن و برای هزینه مبلغ انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            else:
                send_message("لطفا ابتدا یک اتاق را انتخاب کنید", chat_id)
                send_main_menu(chat_id)
        elif message.startswith("eusernames"):
            expense_creation_session = ExpenseCreationSession.objects.filter(user__chat_id=chat_id).first()
            room = expense_creation_session.room
            flag = False
            if expense_creation_session:
                eusernames = message.split("=")[1].strip()
                eusernames_list = eusernames.split(",")
                response = "کاربرانی که انتخاب کردید:\n"
                for username in eusernames_list:
                    user = TelegramUser.objects.filter(username=username.strip()).first()
                    if user and user in room.members.all():
                        expense_creation_session.users.add(user)
                        expense_creation_session.save()
                        response += f"{user.username}\n"
                        flag = True
                        expense_creation_session.participants.add(user)
                    elif user and user not in room.members.all():
                        response += f"{user.username} - این کاربر در این اتاق عضو نیست\n"
                    elif user and user in expense_creation_session.participants.all():
                        response += f"{user.username} - این کاربر قبلا انتخاب شده است\n"
                    else:
                        response += f"{username.strip()} - کاربری یافت نشد\n"
                if flag :
                    expense = Expense.objects.create(
                        room=room,
                        name=expense_creation_session.name,
                        amount=expense_creation_session.amount,
                        description=expense_creation_session.description,
                        payer = expense_creation_session.payer,
                        participants=expense_creation_session.participants.all()
                    )
                    payer = expense.payer
                    amount = expense.amount / len(expense.participants.all())
                    for participant in expense.participants.all():
                        if participant != payer:
                            payment = Payment.objects.create(
                                expense=expense,
                                payer=payer,
                                participant=participant,
                                amount=amount)
                    expense_creation_session.delete()
                    send_message(response, chat_id)
                    send_message("هزینه با موفقیت اضافه شد", chat_id)
                    send_room_main_menu(chat_id, room)
                
                else :
                    send_message("هیچ کاربری انتخاب نشده است", chat_id)
                    send_main_menu(chat_id)
                    expense_creation_session.delete()
            elif expense_creation_session and not expense_creation_session.expense_name:
                send_message("لطفا از ابتدا شروع کن و برای هزینه اسم انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            elif expense_creation_session and not expense_creation_session.expense_amount:
                send_message("لطفا از ابتدا شروع کن و برای هزینه مبلغ انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            elif expense_creation_session and not expense_creation_session.description:
                send_message("لطفا از ابتدا شروع کن و برای هزینه توضیحات انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            else:
                send_message("لطفا ابتدا یک اتاق را انتخاب کنید", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("view_my_debts"):
            user = TelegramUser.objects.filter(chat_id=chat_id).first()
            room_id = message.split("=")[1].strip()
            room = Room.objects.filter(id=room_id).first()
            if room:
                if user:
                    debts = Payment.objects.filter(participant=user)
                    if debts.exists():
                        response = "لیست سود و زیان شما:\n"
                        for debt in debts:
                            response += f"شما باید به {debt.payer.username} {debt.amount} تومان بپردازید\n"
                        send_message(response, chat_id)
                        send_room_main_menu(chat_id, room)
                    else:
                        send_message("شما هیچ سود و زیانی ندارید", chat_id)
                        send_room_main_menu(chat_id, room)
                else:
                    send_message("کاربری یافت نشد", chat_id)
                    send_main_menu(chat_id)
            else:
                send_message("اتاق یافت نشد", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("view_my_credits"):
            user = TelegramUser.objects.filter(chat_id=chat_id).first()
            room_id = message.split("=")[1].strip()
            room = Room.objects.filter(id=room_id).first()
            if room:
                if user:
                    debts = Payment.objects.filter(payer=user)
                    if debts.exists():
                        response = "لیست سود شما:\n"
                        for debt in debts:
                            response += f"شما باید از {debt.participant.username} {debt.amount} تومان بگیرید\n"
                        send_message(response, chat_id)
                        send_room_main_menu(chat_id, room)
                    else:
                        send_message("شما هیچ سودی ندارید")
                        send_room_main_menu(chat_id, room)
                else:
                    send_message("کاربری یافت نشد", chat_id)
                    send_main_menu(chat_id)
            else:
                send_message("اتاق یافت نشد", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("add_room_members"):
            room_id = message.split("=")[1].strip()
            room = Room.objects.filter(id=room_id).first()
            user = TelegramUser.objects.filter(chat_id=chat_id).first()
            if user:
                if room:
                    send_message("لطفا اسم کاربر را به شکل added_username=username انتخاب کنید", chat_id)
                    room_add_member_session = AddRoomMemberSession.objects.filter(user=user).first()
                    if room_add_member_session:
                        room_add_member_session.delete()
                        AddRoomMemberSession.objects.create(room=room, user=user)
                else:
                        send_message("اتاق یافت نشد", chat_id)
                        send_main_menu(chat_id)
            else:
                send_message("کاربری یافت نشد", chat_id)
                send_main_menu(chat_id)

        elif message.startswith("added_username="):
            room_add_member_session = AddRoomMemberSession.objects.filter(user__chat_id=chat_id).first()
            username = message.split("=")[1].strip()
            if room_add_member_session:
                room = room_add_member_session.room
                if room:
                    user = TelegramUser.objects.filter(username=username).first()
                    if user:
                        if user in room.members.all():
                            send_message("کاربر در اتاق وجود دارد", chat_id)
                            room_add_member_session.delete()
                            send_room_main_menu(chat_id, room)
                        else:
                            room.members.add(user)
                            room.save()
                            send_message("کاربر با موفقیت به اتاق اضافه شد", chat_id)
                            room_add_member_session.delete()
                            send_room_main_menu(chat_id, room)
                    else:
                            send_message("کاربر یافت نشد", chat_id)
                            room_add_member_session.delete()
                            send_room_main_menu(chat_id, room)
                else:
                        send_message("اتاق یافت نشد", chat_id)
                        room_add_member_session.delete()
                        send_main_menu(chat_id)
            else:
                    send_message("اتاق و سشن یافت نشد لطقا ازاول امتحان کنید", chat_id)
                    send_main_menu(chat_id)
        elif message == "main_menu":
            send_main_menu(chat_id)

        else:
                send_message("دستور یافت نشد", chat_id)
                send_main_menu(chat_id)



                



                



        
        


            

        
        return HttpResponse('OK', status=200)
    else:
        return HttpResponse('Invalid request method', status=405)