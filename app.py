import os
import re
import secrets
import uuid
from datetime import datetime
from functools import wraps
from html import escape
from urllib.parse import urlparse, parse_qs

from flask import (Flask, render_template, request, redirect, url_for, session,
                   jsonify, flash, abort)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
# o cookie de sessão não é enviado em requisições vindas de outros sites
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


def carregar_chave_secreta():
    """A chave que assina a sessão NÃO fica escrita no código (o repositório é público).
    1) usa a variável de ambiente SECRET_KEY, se existir;
    2) senão, usa (ou cria na primeira execução) o arquivo instance/secret_key.txt,
       que o .gitignore já deixa de fora do GitHub."""
    chave = os.environ.get('SECRET_KEY')
    if chave:
        return chave
    os.makedirs(app.instance_path, exist_ok=True)
    caminho = os.path.join(app.instance_path, 'secret_key.txt')
    if os.path.exists(caminho):
        with open(caminho, encoding='utf-8') as f:
            chave = f.read().strip()
        if chave:
            return chave
    chave = secrets.token_hex(32)
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(chave)
    return chave


app.config['SECRET_KEY'] = carregar_chave_secreta()

# Configuração do upload de arquivos de vídeo
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'videos')
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # limite de 200MB por arquivo
EXTENSOES_PERMITIDAS = {'mp4', 'webm', 'ogg', 'mov'}
PREFIXO_UPLOAD = '/static/videos/'

# Limites usados na validação dos formulários
TITULO_MAX = 120
DESCRICAO_MAX = 300
LINK_MAX = 300
LIMITE_COMENTARIO = 300
SENHA_MIN = 6
SENHA_MAX = 128
USERNAME_REGEX = re.compile(r'^[A-Za-z0-9_.-]{3,30}$')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)


# ---------------------------------------------------------------- MODELOS

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)   # guarda o hash, nunca a senha


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(TITULO_MAX), nullable=False)
    descricao = db.Column(db.String(DESCRICAO_MAX), nullable=True)
    link = db.Column(db.String(LINK_MAX), nullable=False)
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

def login_obrigatorio(rota):
    """Protege as páginas: quem não está logado volta pra tela de login."""
    @wraps(rota)
    def protegida(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return rota(*args, **kwargs)
    return protegida


def exige_login_json():
    """Pras rotas que respondem JSON: devolve um erro 401 se não tiver ninguém logado."""
    if 'user_id' not in session:
        return jsonify({'erro': 'Faça login para continuar.'}), 401
    return None


@app.context_processor
def dados_globais():
    # deixa o nome de quem está logado disponível em todos os templates
    return {'username_logado': session.get('username')}


def extensao_permitida(nome_arquivo):
    return '.' in nome_arquivo and nome_arquivo.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS


def link_valido(link):
    partes = urlparse(link)
    return partes.scheme in ('http', 'https') and bool(partes.netloc)


def validar_cadastro(username, senha):
    """Devolve a mensagem de erro, ou None se estiver tudo certo."""
    if not USERNAME_REGEX.match(username):
        return 'O usuário deve ter de 3 a 30 caracteres: letras, números, ponto, hífen ou underline.'
    if len(senha) < SENHA_MIN:
        return f'A senha precisa ter pelo menos {SENHA_MIN} caracteres.'
    if len(senha) > SENHA_MAX:
        return f'A senha pode ter no máximo {SENHA_MAX} caracteres.'
    return None


def validar_video(titulo, descricao, link):
    """Devolve a mensagem de erro, ou None se estiver tudo certo.
    Passe link=None quando o vídeo for um arquivo enviado (não tem link pra conferir)."""
    if not titulo:
        return 'Informe um título para o vídeo.'
    if len(titulo) > TITULO_MAX:
        return f'O título pode ter no máximo {TITULO_MAX} caracteres.'
    if len(descricao) > DESCRICAO_MAX:
        return f'A descrição pode ter no máximo {DESCRICAO_MAX} caracteres.'
    if link is not None:
        if len(link) > LINK_MAX:
            return f'O link pode ter no máximo {LINK_MAX} caracteres.'
        if not link_valido(link):
            return 'Informe um link completo, começando com http:// ou https://'
    return None


def apagar_arquivo_enviado(link):
    """Se o vídeo era um arquivo enviado, apaga o arquivo do disco.
    Só mexe dentro da pasta de uploads (basename impede caminhos como ../)."""
    if not link.startswith(PREFIXO_UPLOAD):
        return
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(link))
    if os.path.isfile(caminho):
        os.remove(caminho)


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


def video_para_dict(v):
    """Dados de um vídeo prontos pros cards do painel e do perfil."""
    return {
        'id': v.id,
        'titulo': v.titulo,
        'descricao': v.descricao,
        'autor': v.usuario.username,
        'meu': v.usuario_id == session['user_id'],
        'embed': gerar_embed(v.link),
        'curtidas': Curtida.query.filter_by(video_id=v.id).count(),
        'comentarios': Comentario.query.filter_by(video_id=v.id).count(),
    }


def comentario_para_dict(c):
    return {
        'id': c.id,
        'autor': c.usuario.username,
        'texto': c.texto,
        'data': c.data.strftime('%d/%m/%Y %H:%M'),
        'meu': c.usuario_id == session['user_id'],   # só o autor vê o botão de excluir
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


# ---------------------------------------------------------------- LOGIN / CADASTRO

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        senha = request.form.get('password', '')
        user = Usuario.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, senha):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('painel'))
        flash('Usuário ou senha incorretos.', 'erro')
        return redirect(url_for('index'))
    if 'user_id' in session:
        return redirect(url_for('painel'))
    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        senha = request.form.get('password', '')

        erro = validar_cadastro(username, senha)
        if erro:
            flash(erro, 'erro')
            return redirect(url_for('cadastro'))

        if Usuario.query.filter_by(username=username).first():
            flash('Esse nome de usuário já existe! Escolha outro.', 'erro')
            return redirect(url_for('cadastro'))

        try:
            db.session.add(Usuario(username=username, password=generate_password_hash(senha)))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()   # duas pessoas cadastrando o mesmo nome ao mesmo tempo
            flash('Esse nome de usuário já existe! Escolha outro.', 'erro')
            return redirect(url_for('cadastro'))

        flash('Conta criada com sucesso! Faça login para entrar.', 'sucesso')
        return redirect(url_for('index'))
    return render_template('cadastro.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'sucesso')
    return redirect(url_for('index'))


# ---------------------------------------------------------------- PAINEL, PERFIL E VÍDEOS

@app.route('/painel')
@login_obrigatorio
def painel():
    videos = Video.query.order_by(Video.id.desc()).all()
    return render_template('painel.html', videos=[video_para_dict(v) for v in videos])


@app.route('/perfil')
@login_obrigatorio
def meu_perfil():
    return redirect(url_for('perfil', username=session['username']))


@app.route('/perfil/<username>')
@login_obrigatorio
def perfil(username):
    dono = Usuario.query.filter_by(username=username).first()
    if dono is None:
        abort(404)

    videos = Video.query.filter_by(usuario_id=dono.id).order_by(Video.id.desc()).all()
    videos_formatados = [video_para_dict(v) for v in videos]
    resumo = {
        'videos': len(videos_formatados),
        'curtidas_recebidas': sum(v['curtidas'] for v in videos_formatados),
        'comentarios_feitos': Comentario.query.filter_by(usuario_id=dono.id).count(),
    }
    return render_template(
        'perfil.html',
        dono=dono,
        videos=videos_formatados,
        resumo=resumo,
        eh_meu=(dono.id == session['user_id']),
        voltar_para='perfil',
    )


@app.route('/cadastrar-video', methods=['GET', 'POST'])
@login_obrigatorio
def cadastrar_video():
    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        link = request.form.get('link', '').strip()
        arquivo = request.files.get('arquivo')
        enviou_arquivo = bool(arquivo and arquivo.filename)

        # tudo é conferido ANTES de salvar o arquivo, pra não sobrar arquivo solto no disco
        if enviou_arquivo:
            if not extensao_permitida(arquivo.filename):
                flash('Formato não suportado! Envie um arquivo .mp4, .webm, .ogg ou .mov', 'erro')
                return redirect(url_for('cadastrar_video'))
            erro = validar_video(titulo, descricao, None)
        elif not link:
            erro = 'Informe um link OU envie um arquivo de vídeo!'
        else:
            erro = validar_video(titulo, descricao, link)

        if erro:
            flash(erro, 'erro')
            return redirect(url_for('cadastrar_video'))

        if enviou_arquivo:
            nome_unico = f"{uuid.uuid4().hex}_{secure_filename(arquivo.filename)}"
            arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], nome_unico))
            link_final = url_for('static', filename=f'videos/{nome_unico}')
        else:
            link_final = link

        db.session.add(Video(titulo=titulo, descricao=descricao, link=link_final,
                             usuario_id=session['user_id']))
        db.session.commit()
        flash('Vídeo cadastrado com sucesso!', 'sucesso')
        return redirect(url_for('painel'))
    return render_template('cadastro_video.html')


@app.route('/video/<int:video_id>/editar', methods=['GET', 'POST'])
@login_obrigatorio
def editar_video(video_id):
    video = db.get_or_404(Video, video_id)
    if video.usuario_id != session['user_id']:
        flash('Você só pode editar os seus próprios vídeos.', 'erro')
        return redirect(url_for('pagina_video', video_id=video.id))

    # vídeo enviado do computador: o arquivo não muda, só título e descrição
    arquivo_enviado = video.link.startswith(PREFIXO_UPLOAD)

    if request.method == 'POST':
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        link = None if arquivo_enviado else request.form.get('link', '').strip()

        erro = validar_video(titulo, descricao, link)
        if erro:
            flash(erro, 'erro')
            return redirect(url_for('editar_video', video_id=video.id))

        video.titulo = titulo
        video.descricao = descricao
        if link is not None:
            video.link = link
        db.session.commit()
        flash('Vídeo atualizado com sucesso!', 'sucesso')
        return redirect(url_for('pagina_video', video_id=video.id))

    return render_template('editar_video.html', video=video, arquivo_enviado=arquivo_enviado)


@app.route('/video/<int:video_id>/excluir', methods=['POST'])
@login_obrigatorio
def excluir_video(video_id):
    video = db.get_or_404(Video, video_id)
    if video.usuario_id != session['user_id']:
        flash('Você só pode excluir os seus próprios vídeos.', 'erro')
        return redirect(url_for('pagina_video', video_id=video.id))

    link = video.link
    # apaga junto os comentários e as curtidas do vídeo, pra não sobrar registro solto
    for comentario in Comentario.query.filter_by(video_id=video.id).all():
        db.session.delete(comentario)
    for curtida in Curtida.query.filter_by(video_id=video.id).all():
        db.session.delete(curtida)
    db.session.delete(video)
    db.session.commit()
    apagar_arquivo_enviado(link)

    flash('Vídeo excluído.', 'sucesso')
    if request.form.get('voltar_para') == 'perfil':
        return redirect(url_for('perfil', username=session['username']))
    return redirect(url_for('painel'))


# ---------------------------------------------------------------- PÁGINA DO VÍDEO, CURTIDAS E COMENTÁRIOS

@app.route('/video/<int:video_id>')
@login_obrigatorio
def pagina_video(video_id):
    video = db.get_or_404(Video, video_id)
    return render_template(
        'video.html',
        video=video,
        embed=gerar_embed(video.link),
        eh_dono=(video.usuario_id == session['user_id']),
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


@app.route('/comentario/<int:comentario_id>/excluir', methods=['POST'])
def excluir_comentario(comentario_id):
    erro = exige_login_json()
    if erro:
        return erro
    comentario = db.get_or_404(Comentario, comentario_id)
    if comentario.usuario_id != session['user_id']:
        return jsonify({'erro': 'Você só pode excluir os seus próprios comentários.'}), 403

    video = db.get_or_404(Video, comentario.video_id)
    db.session.delete(comentario)
    db.session.commit()
    return jsonify(dados_interacao(video))


# ---------------------------------------------------------------- PÁGINAS DE ERRO

@app.errorhandler(404)
def pagina_nao_encontrada(e):
    return render_template('erro.html', titulo='Página não encontrada',
                           mensagem='Esse endereço não existe ou o conteúdo foi removido.'), 404


@app.errorhandler(413)
def arquivo_muito_grande(e):
    flash('Arquivo muito grande! O limite é de 200MB.', 'erro')
    return redirect(url_for('cadastrar_video'))


if __name__ == '__main__':
    # o modo debug só liga se você pedir (set FLASK_DEBUG=1), nunca por padrão
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
