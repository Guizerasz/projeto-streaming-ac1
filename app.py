import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'troque-essa-chave-por-uma-aleatoria'

# Configuração do upload de arquivos de vídeo
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'videos')
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # limite de 200MB por arquivo
EXTENSOES_PERMITIDAS = {'mp4', 'webm', 'ogg', 'mov'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.String(300), nullable=True)
    link = db.Column(db.String(300), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)


with app.app_context():
    db.create_all()


def extensao_permitida(nome_arquivo):
    return '.' in nome_arquivo and nome_arquivo.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS


def gerar_embed(link):
    """Recebe o link/caminho salvo e devolve o HTML certo pra exibir o vídeo:
    iframe do YouTube se for um link do YouTube, ou tag de vídeo direta caso
    contrário (arquivo enviado pelo usuário, mp4 hospedado em outro site, etc)."""
    video_id = None

    if 'youtu.be' in link:
        video_id = link.split('/')[-1].split('?')[0]
    elif 'youtube.com' in link:
        partes = urlparse(link)
        video_id = parse_qs(partes.query).get('v', [None])[0]

    if video_id:
        return (
            f'<iframe class="w-full aspect-video rounded" '
            f'src="https://www.youtube.com/embed/{video_id}" '
            f'frameborder="0" allowfullscreen></iframe>'
        )

    return (
        f'<video class="w-full aspect-video rounded bg-black" controls>'
        f'<source src="{link}">'
        f'Seu navegador não suporta vídeo.</video>'
    )


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('painel'))
        else:
            return "<script>alert('Usuário ou senha incorretos!'); window.location='/';</script>"
    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        usuario_existente = Usuario.query.filter_by(username=request.form['username']).first()
        if usuario_existente:
            return "<script>alert('Esse nome de usuário já existe! Escolha outro.'); window.location='/cadastro';</script>"
        senha_hash = generate_password_hash(request.form['password'])
        novo_user = Usuario(username=request.form['username'], password=senha_hash)
        db.session.add(novo_user)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('cadastro.html')


@app.route('/painel')
def painel():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    videos = Video.query.order_by(Video.id.desc()).all()
    videos_formatados = [
        {
            'titulo': v.titulo,
            'descricao': v.descricao,
            'embed': gerar_embed(v.link),
        }
        for v in videos
    ]
    return render_template('painel.html', username=session['username'], videos=videos_formatados)


@app.route('/cadastrar-video', methods=['GET', 'POST'])
def cadastrar_video():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        link = request.form.get('link', '').strip()
        arquivo = request.files.get('arquivo')

        link_final = None

        # Prioridade pro arquivo enviado, se tiver um selecionado
        if arquivo and arquivo.filename != '':
            if not extensao_permitida(arquivo.filename):
                return "<script>alert('Formato não suportado! Envie um arquivo .mp4, .webm, .ogg ou .mov'); window.location='/cadastrar-video';</script>"

            nome_original_seguro = secure_filename(arquivo.filename)
            nome_unico = f"{uuid.uuid4().hex}_{nome_original_seguro}"
            caminho_no_disco = os.path.join(app.config['UPLOAD_FOLDER'], nome_unico)
            arquivo.save(caminho_no_disco)
            link_final = url_for('static', filename=f'videos/{nome_unico}')
        elif link:
            link_final = link

        if not link_final:
            return "<script>alert('Informe um link OU envie um arquivo de vídeo!'); window.location='/cadastrar-video';</script>"

        novo_video = Video(
            titulo=request.form['titulo'],
            descricao=request.form.get('descricao', ''),
            link=link_final,
            usuario_id=session['user_id'],
        )
        db.session.add(novo_video)
        db.session.commit()
        return redirect(url_for('painel'))
    return render_template('cadastro_video.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
