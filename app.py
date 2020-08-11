from flask import Flask, session, redirect, render_template, request, flash, url_for, json
from flask_socketio import SocketIO, emit, join_room
from flask_login import UserMixin, LoginManager, login_required, current_user, login_user, logout_user
from dbModel import UserAccounts, Message, db
from functools import wraps
from PIL import Image
from datetime import datetime
import base64
import os
import uuid
import io

MugShot_PATH = 'static/mugshot'
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
MugShot_FOLDER = os.path.join(APP_ROOT, MugShot_PATH)

app = Flask(__name__)
app.secret_key = 'super secret string'  # Change this!
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = "strong"
login_manager.login_view = "login"
login_manager.login_message = "Please LOG IN"
login_manager.login_message_category = "info"

socketio = SocketIO(app)
async_mode = "eventlet"

dbModel_stock = list()

class User(UserMixin):
    pass


def to_json(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        get_fun = func(*args, **kwargs)
        return json.dumps(get_fun)

    return wrapper


def query_user(username):
    user = UserAccounts.query.filter_by(UserName=username).first()
    if user:
        return True
    return False


def dynamic_dbModel(tableName):
    def initFunc(self,
                 user_name,
                 messages,
                 create_date):
        self.UserName = user_name
        self.Messages = messages
        self.CreateDate = create_date

    tableDict={'Id':db.Column(db.Integer, primary_key=True),
               'UserName':db.Column(db.String(64)),
               'Messages':db.Column(db.Text),
               'CreateDate':db.Column(db.DateTime),
               '__tablename__':tableName,
               '__init__':initFunc}

    newClass = type(tableName, (db.Model,), tableDict)
    dbModel_stock.append(newClass)
    return newClass


def create_messageTable(username):
    newClass = dynamic_dbModel('Message__' + username)
    for clazz in db.Model._decl_class_registry.values():
        print('[INFO] ' + str(clazz))
    db.create_all()
    db.session.commit()
    print('[INFO] db.create_all')
    for clazz in db.Model._decl_class_registry.values():
        print('[INFO] ' + str(clazz))


def get_messageTable(username):
    targetTable = None
    for clazz in db.Model._decl_class_registry.values():
        print('[INFO] ' + str(clazz))
        try:
            print('[INFO] ' + str(clazz.__tablename__))
            if clazz.__tablename__ == 'Message__' + username:
                targetTable = clazz
        except:
            pass
    if not targetTable:
        targetTable = dynamic_dbModel('Message__' + username)
    return targetTable


@login_manager.user_loader
def user_loader(username):
    if query_user(username):
        user = User()
        user.id = username
        return user
    return None

@app.after_request
def apply_caching(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

@app.route('/test_point', methods=['GET'])
def test_point():
    print(db.Model._decl_class_registry)
    vals = db.Model._decl_class_registry.values()
    for val in vals:
        print(val)
    
    print(dir(db.Model))
    return "OK"


@app.route('/')
@app.route('/index', methods=['GET'])
@login_required
def index():
    user_id = session.get('user_id')
    messageClass = get_messageTable(user_id)

    message_data = db.session.query(
        messageClass,
        UserAccounts.MugShot
    ).join(
        UserAccounts,
        UserAccounts.UserName == messageClass.UserName
    ).all()

    mug_shot_title = UserAccounts.query.filter_by(UserName=user_id).first().MugShot
    messages_dic = {}
    messages_list = []
    for message in message_data:
        messages_dic['data'] = []
        object_data = getattr(message, 'Message__' + user_id)
        messages_dic['UserName'] = object_data.UserName
        messages_dic['Messages'] = object_data.Messages
        messages_dic['MugShot'] = message.MugShot
        messages_dic['CreateDate'] = object_data.CreateDate.strftime('%H:%M')
        messages_list.append(messages_dic)
        messages_dic = {}
    return render_template("index.html", **locals())


@app.route('/login', methods=['GET', 'POST'])
def login():
    user_id = session.get('user_id')

    if request.method == 'GET':
        return render_template("login.html")

    if current_user.is_authenticated and query_user(user_id):
        return redirect(url_for('index'))

    username = request.form['username']
    user = UserAccounts.query.filter_by(UserName=username).first()
    if not user:
        return render_template("login.html", error="username or password error")
    pw_form = UserAccounts.psw_to_md5(request.form['password'])
    pw_db = user.Password
    if pw_form == pw_db:
        user = User()
        user.id = username
        login_user(user, remember=True)
        flash('Logged in successfully')
        return redirect(url_for('index'))
    return render_template("login.html", error="username or password error")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template("register.html")
    username = request.form['username']
    password = request.form['password']
    new_account = UserAccounts(user_name=username, password=password, mugshot="default.jpg")
    db.session.add(new_account)
    db.session.commit()
    create_messageTable(username)
    return redirect(url_for("index"))


@app.route('/API_check_UserNameExist', methods=['POST'])
@to_json
def api_check_user_name_exist():
    username = request.json['username']
    user = UserAccounts.query.filter_by(UserName=username).first()
    if not user:
        return "not_exist"
    return "exist"


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@socketio.on('join')
def join(message):
    user_id = session.get('user_id')
    join_room(user_id)
    print('join')


@socketio.on('connect')
def test_connect():
    # Userid = session.get('UserId')
    # print(Userid, 'connectd')
    print('connect')


@socketio.on('sendInquiry')
def send_inquiry(msg):
    user_id = session.get('user_id')
    create_date = datetime.now()
    messageClass = get_messageTable(user_id)

    data_message = messageClass(
        user_name=user_id,
        messages=msg['msg'],
        create_date=create_date
    )
    db.session.add(data_message)
    db.session.commit()
    mug_shot = UserAccounts.query.filter_by(UserName=user_id).first().MugShot
    data = {
        'time': create_date.strftime('%H:%M'),
        'Name': user_id,
        'PictureUrl': mug_shot,
        'msg': msg['msg'],
    }
    emit('getInquiry', data, room=user_id)


@app.route('/croppic', methods=['GET', 'POST'])
def croppic():
    user_id = session.get('user_id')
    try:
        # imgUrl 		// your image path (the one we recieved after successfull upload)
        img_url = request.form['imgUrl']
        # imgInitW  	// your image original width (the one we recieved after upload)
        # img_init_w = request.form['imgInitW']
        # imgInitH 	    // your image original height (the one we recieved after upload)
        # img_init_h = request.form['imgInitH']
        # imgW 		    // your new scaled image width
        img_w = request.form['imgW']
        # imgH 		    // your new scaled image height
        img_h = request.form['imgH']
        # imgX1 		// top left corner of the cropped image in relation to scaled image
        img_x1 = request.form['imgX1']
        # imgY1 		// top left corner of the cropped image in relation to scaled image
        img_y1 = request.form['imgY1']
        # cropW 		// cropped image width
        crop_w = request.form['cropW']
        # cropH 		// cropped image height
        crop_h = request.form['cropH']
        angle = request.form['rotation']

        # original size
        # imgInitW, imgInitH = int(img_init_w), int(img_init_h)

        # Adjusted size
        img_w, img_h = int(float(img_w)), int(float(img_h))
        img_y1, img_x1 = int(float(img_y1)), int(float(img_x1))
        crop_w, crop_h = int(float(crop_w)), int(float(crop_h))
        angle = int(angle)

        # image_format = imgUrl.split(';base64,')[0].split('/')[1]
        # title_head = img_url.split(',')[0]
        img_data = img_url.split('base64,')[1]
        img_data = base64.b64decode(img_data)

        source_image = Image.open(io.BytesIO(img_data))
        image_format = source_image.format.lower()
        # create new crop image
        source_image = source_image.resize((img_w, img_h), Image.ANTIALIAS)

        rotated_image = source_image.rotate(-float(angle), Image.BICUBIC)
        rotated_width, rotated_height = rotated_image.size
        dx = rotated_width - img_w
        dy = rotated_height - img_h
        cropped_rotated_image = Image.new('RGBA', (img_w, img_h))
        cropped_rotated_image.paste(rotated_image.crop((dx / 2, dy / 2, dx / 2 + img_w, dy / 2 + img_h)),
                                    (0, 0, img_w, img_h))

        final_image = Image.new('RGBA', (crop_w, crop_h), 0)
        final_image.paste(cropped_rotated_image.crop((img_x1, img_y1, img_x1 + crop_w, img_y1 + crop_h)),
                          (0, 0, crop_w, crop_h))

        uuid_name = str(uuid.uuid1())
        mugshot = '{}.{}'.format(uuid_name, image_format)
        user_mugshot = UserAccounts.query.filter_by(UserName=user_id).first()
        if user_mugshot.MugShot != "default.jpg":
            delete_filename = '{}/{}'.format(MugShot_FOLDER, user_mugshot.MugShot)
            os.remove(delete_filename)

        user_mugshot.MugShot = mugshot
        db.session.commit()
        save_path = '{}/{}'.format(MugShot_FOLDER, mugshot)
        final_image.save(save_path)

        #  The crop rectangle, as a (left, upper, right, lower)-tuple.
        # box = (imgX1, imgY1, imgX1 + cropW, imgY1 + cropH)
        # newImg = source_image.crop(box)
        # imgByteArr = io.BytesIO()
        # newImg.save(imgByteArr, format=image_format)
        # imgByteArr = imgByteArr.getvalue()
        # imgbase = base64.b64encode(imgByteArr).decode('utf-8')
        # img_base64 = '{},{}'.format(title_head, imgbase)

        data = {
            'status': 'success',
            'url': '/{}/{}'.format(MugShot_PATH, mugshot),
            'filename': mugshot
        }
        return json.dumps(data)
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
        }


if __name__ == '__main__':
    socketio.run(app, debug='true', host='0.0.0.0', port=8787)