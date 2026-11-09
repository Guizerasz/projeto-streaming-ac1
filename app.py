import os
import uuid
from datetime import datetime
from html import escape
from urllib.parse import urlparse, parse_qs

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'troque-essa-chave-por-uma-aleatoria'

# Configuração do upload de arquivos de vídeo
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'videos')
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # limite de 200MB por arquivo
EXTENSOES_PERMITIDAS = {'mp4', 'webm', 'ogg', 'mov'}
LIMITE_COMENTARIO = 300

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# ---------------------------------------------------------------- MODELOS

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
    usuario = db.relationship('Usuario')


class Comentario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(LIMITE_COMENTARIO), nullable=False)
    data = db.Column(db.DateTime, default=datetime.now)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    usuario = db.relationship('Usuario')


class Curtida(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    # garante que cada usuário curte um vídeo no máximo uma vez
    __table_args__ = (db.UniqueConstraint('video_id', 'usuario_id', name='uma_curtida_por_usuario'),)


with app.app_context():
    db.create_all()


# ---------------------------------------------------------------- FUNÇÕES AUXILIARES

def extensao_permitida(nome_arquivo):
    return '.' in nome_arquivo and nome_arquivo.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS


def gerar_embed(link):
    """Recebe o link/caminho salvo e devolve o HTML certo pra exibir o vídeo:
    iframe do YouTube se for um link do YouTube, ou tag de vídeo direta caso
    contrário (arquivo enviado pelo usuário, mp4 hospedado em outro site, etc).
    Tudo que vem do usuário passa por escape() pra não dar pra injetar HTML."""
    video_id = None

    if 'youtu.be' in link:
        video_id = link.split('/')[-1].split('?')[0]
    elif 'youtube.com' in link:
        partes = urlparse(link)
        video_id = parse_qs(partes.query).get('v', [None])[0]

    if video_id:
        return (
            f'<iframe class="w-full aspect-video rounded" '
            f'src="https://www.youtube.com/embed/{escape(video_id, quote=True)}" '
            f'frameborder="0" allowfullscreen></iframe>'
        )

    return (
        f'<video class="w-full aspect-video rounded bg-black" controls>'
        f'<source src="{escape(link, quote=True)}">'
        f'Seu navegador não suporta vídeo.</video>'
    )


def comentario_para_dict(c):
    return {
        'id': c.id,
        'autor': c.usuario.username,
        'texto': c.texto,
        'data': c.data.strftime('%d/%m/%Y %H:%M'),
    }


def dados_interacao(video):
    """Tudo que a página do vídeo precisa pra se atualizar: total de curtidas,
    se o usuário logado já curtiu, e a lista de comentários (mais novo primeiro)."""
    curtidas = Curtida.query.filter_by(video_id=video.id).count()
    curtido = Curtida.query.filter_by(video_id=video.id, usuario_id=session['user_id']).first() is not None
    comentarios = Comentario.query.filter_by(video_id=video.id).order_by(Comentario.id.desc()).all()
    return {
        'curtidas': curtidas,
        'curtido': curtido,
        'comentarios': [comentario_para_dict(c) for c in comentarios],
    }


def exige_login_json():
    """Pras rotas que respondem JSON: devolve um erro 401 se não tiver ninguém logado."""
    if 'user_id' not in session:
        return jsonify({'erro': 'Faça login para continuar.'}), 401
    return None


# ---------------------------------------------------------------- LOGIN / CADASTRO

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


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ---------------------------------------------------------------- PAINEL E VÍDEOS

@app.route('/painel')
def painel():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    videos = Video.query.order_by(Video.id.desc()).all()
    videos_formatados = [
        {
            'id': v.id,
            'titulo': v.titulo,
            'descricao': v.descricao,
            'autor': v.usuario.username,
            'embed': gerar_embed(v.link),
            'curtidas': Curtida.query.filter_by(video_id=v.id).count(),
            'comentarios': Comentario.query.filter_by(video_id=v.id).count(),
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


# ---------------------------------------------------------------- PÁGINA DO VÍDEO (AC3)

@app.route('/video/<int:video_id>')
def pagina_video(video_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    video = db.get_or_404(Video, video_id)
    return render_template(
        'video.html',
        username=session['username'],
        video=video,
        embed=gerar_embed(video.link),
        limite=LIMITE_COMENTARIO,
    )


@app.route('/video/<int:video_id>/interacoes')
def interacoes(video_id):
    """A página do vídeo chama essa rota de tempos em tempos pra mostrar
    curtidas e comentários novos de outras pessoas sem precisar recarregar."""
    erro = exige_login_json()
    if erro:
        return erro
    video = db.get_or_404(Video, video_id)
    return jsonify(dados_interacao(video))


@app.route('/video/<int:video_id>/curtir', methods=['POST'])
def curtir(video_id):
    erro = exige_login_json()
    if erro:
        return erro
    video = db.get_or_404(Video, video_id)

    curtida = Curtida.query.filter_by(video_id=video.id, usuario_id=session['user_id']).first()
    try:
        if curtida:
            db.session.delete(curtida)   # já tinha curtido: clicar de novo descurte
        else:
            db.session.add(Curtida(video_id=video.id, usuario_id=session['user_id']))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()            # clique duplo muito rápido: ignora, o estado já está certo

    return jsonify(dados_interacao(video))


@app.route('/video/<int:video_id>/comentar', methods=['POST'])
def comentar(video_id):
    erro = exige_login_json()
    if erro:
        return erro
    video = db.get_or_404(Video, video_id)

    dados = request.get_json(silent=True) or {}
    texto = (dados.get('texto') or '').strip()

    if not texto:
        return jsonify({'erro': 'Escreva algo antes de comentar.'}), 400
    if len(texto) > LIMITE_COMENTARIO:
        return jsonify({'erro': f'O comentário pode ter no máximo {LIMITE_COMENTARIO} caracteres.'}), 400

    db.session.add(Comentario(texto=texto, video_id=video.id, usuario_id=session['user_id']))
    db.session.commit()
    return jsonify(dados_interacao(video)), 201


if __name__ == '__main__':
    app.run(debug=True)
