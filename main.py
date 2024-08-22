from flask import Flask, abort, render_template, redirect, url_for, flash, request, session
from flask_sqlalchemy import SQLAlchemy
import datetime
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from forms import RegisterForm, LoginForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bootstrap import Bootstrap5
from sqlalchemy import cast, Date
from operator import itemgetter, attrgetter

app = Flask(__name__)
Bootstrap5(app)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todolist.db'
db = SQLAlchemy()
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.session_protection = "strong"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    list_created = db.relationship('Lists', backref='author', lazy=True)
    task_created = db.relationship('Tasks', backref='author', lazy=True)


class Lists(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    list_name = db.Column(db.String(200), unique=True, nullable=False)
    list_create_date = db.Column(db.Date, default=datetime.datetime.today())
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    task_created = db.relationship('Tasks', backref='list_created', lazy=True)


class Tasks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(500))
    task_due_date = db.Column(db.Date)
    task_create_date = db.Column(db.Date, default=datetime.datetime.today())
    status = db.Column(db.String(100))
    list_id = db.Column(db.Integer, db.ForeignKey("lists.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    # list_created = db.relationship('Lists', backref='task_created', lazy=True)
    # author = db.relationship('User', backref='task_created', lazy=True)


with app.app_context():
    db.create_all()


#
# with app.app_context():
#     user = db.session.execute(db.select(User).where(User.id == 1)).scalar()
#     for n in user.list_created:
#         print(n.list_name, n.list_create_date)


@app.route('/', methods=['GET', 'POST'])
def home():
    if current_user.is_authenticated:
        lists = db.session.execute(db.select(User).where(User.id == current_user.id)).scalar().list_created

        if request.method == 'POST':
            if 'change_list_name' in request.form:
                list_id = request.args.get('list_id_update')
                new_name = request.form.get('update_list_name')
                list_update = db.session.execute(
                    db.select(Lists).where(Lists.id == list_id)).scalar()
                list_update.list_name = new_name
                db.session.commit()
                lists = db.session.execute(db.select(User).where(User.id == current_user.id)).scalar().list_created
                return render_template('index.html', lists=lists)
            elif 'create_list' in request.form:
                new_list = Lists(
                    list_name=request.form.get('new_list'),
                    user_id=current_user.id
                )
                db.session.add(new_list)
                db.session.commit()
                new_list_id = db.session.execute(
                    db.select(Lists).where(Lists.list_name == request.form.get('new_list'))).scalar().id
                return redirect(url_for('add_tasks', list_id=new_list_id))
        return render_template('index.html', lists=lists)
    else:
        form = LoginForm()
        if form.validate_on_submit():
            user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
            if user:
                if check_password_hash(user.password, form.password.data):
                    login_user(user)
                    flash('You have successfully logged in.')
                    return redirect(url_for('home'))
                else:
                    flash('Wrong password. Please try again.')
                    return redirect(url_for('home'))
            else:
                flash('You have not registered with this email. Please register first.')
                return redirect(url_for('register'))
        return render_template('login.html', form=form)


@app.route('/add_tasks/<int:list_id>', methods=['GET', 'POST'])
def add_tasks(list_id):
    lists = db.session.execute(db.select(User).where(User.id == current_user.id)).scalar().list_created
    list = db.session.execute(db.select(Lists).where(Lists.id == list_id)).scalar()

    def multisort(xs, specs):
        for key, reverse in reversed(specs):
            xs.sort(key=attrgetter(key), reverse=reverse)
        return xs

    task = multisort((list.task_created), (('status', True), ('task_due_date', False)))
    if request.method == 'POST':
        if "update_tasks" in request.form:
            for n in task:
                n.status = 'todo'
                db.session.commit()
            checkbox = request.form.getlist('task_status')
            completed = db.session.query(Tasks).filter(Tasks.id.in_(checkbox)).all()
            for n in completed:
                n.status = 'completed'
                db.session.commit()
            task = multisort((list.task_created), (('status', True), ('task_due_date', False)))
        elif 'create_task' in request.form:
            dd = request.form.get('due_date')
            year, month, day = dd.split('-')
            due_date = datetime.date(int(year), int(month), int(day))
            new_task = Tasks(
                task=request.form.get('task_name'),
                task_due_date=due_date,
                status='todo',
                list_id=list_id,
                user_id=current_user.id
            )
            db.session.add(new_task)
            db.session.commit()
            task = multisort((list.task_created), (('status', True), ('task_due_date', False)))
    return render_template('index_tasks.html', lists=lists, new_list=list, tasks=task)


@app.route('/change_tasks/<int:list_id>/<int:task_id>', methods=['GET', 'POST'])
def change_tasks(list_id, task_id):
    if request.method == 'POST':
        new_name = request.form.get('update_task_name')
        new_due_date = request.form.get('new_due_date')
        if new_due_date:
            year, month, day = new_due_date.split('-')
            new_due_date = datetime.date(int(year), int(month), int(day))
            task_update = db.session.execute(
                db.select(Tasks).where(Tasks.id == task_id)).scalar()
            task_update.task = new_name
            task_update.task_due_date = new_due_date
            db.session.commit()
        else:
            task_update = db.session.execute(
                db.select(Tasks).where(Tasks.id == task_id)).scalar()
            task_update.task = new_name
            db.session.commit()

    return redirect(url_for('add_tasks', list_id=list_id))


@app.route('/delete_list', methods=['GET', 'POST'])
def delete_list():
    list_id = request.args.get('id')
    list_delete = db.session.execute(db.select(Lists).where(Lists.id == list_id)).scalar()
    tasks = [n.id for n in list_delete.task_created]
    tasks_delete = db.session.execute(db.select(Tasks).where(Tasks.id.in_(tasks))).scalars().all()
    db.session.delete(list_delete)
    db.session.commit()
    for n in tasks_delete:
        db.session.delete(n)
        db.session.commit()
    return redirect(url_for('home'))


@app.route('/delete_tasks', methods=['GET', 'POST'])
def delete_tasks():
    task_id = request.args.get('id')
    list_id = request.args.get('list_id')
    tasks_delete = db.session.execute(db.select(Tasks).where(Tasks.id == task_id)).scalar()
    db.session.delete(tasks_delete)
    db.session.commit()
    return redirect(url_for('add_tasks', list_id=list_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if not user:
            hash_password = generate_password_hash(form.password.data)
            new_user = User(
                email=form.email.data,
                password=hash_password
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('You have successfully logged in.')
            return redirect(url_for('home'))
        else:
            flash('You have registered with this email. Please log in instead.')
            return redirect(url_for('home'))
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    session.pop('_flashes', None)
    logout_user()
    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)
