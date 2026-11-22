# StreamHub — Plataforma de Streaming (Projeto Acadêmico)

Plataforma de streaming fictícia desenvolvida em Python com Flask. Os usuários criam conta, publicam vídeos (por link do YouTube ou enviando um arquivo), interagem por curtidas e comentários e têm uma página de perfil com os próprios vídeos.

## Funcionalidades

**Usuários (AC1)**
- Cadastro de novos usuários, com validação (usuário de 3 a 30 caracteres, senha de 6 a 128) e aviso quando o nome já existe
- Login com sessão e logout
- Senhas armazenadas com hash (Werkzeug), nunca em texto puro

**Vídeos (AC2)**
- Cadastro de vídeo com título, descrição e link do YouTube ou arquivo enviado do computador (.mp4, .webm, .ogg, .mov)
- Reconhecimento automático de links do YouTube, com player embutido
- Listagem dos vídeos no painel, do mais novo para o mais antigo

**Interação (AC3)**
- Página própria para cada vídeo
- Curtir e descurtir (uma curtida por usuário em cada vídeo)
- Comentários de até 300 caracteres, com autor e data
- Atualização sem recarregar a página (curtidas e comentários de outras pessoas aparecem sozinhos em poucos segundos)

**Versão final (prova)**
- **Editar e excluir vídeos** — só o autor pode; ao excluir, os comentários, as curtidas e o arquivo enviado também são apagados
- **Excluir os próprios comentários** — o botão só aparece para o autor do comentário
- **Página de perfil** — "Meus vídeos" com total de vídeos, curtidas recebidas e comentários feitos; também dá para ver o perfil de outros usuários
- **Validações no backend** — tamanhos, link http/https, formato de arquivo e limite de upload (200MB)
- **Mensagens amigáveis** (sucesso e erro) no lugar de alert() e telas de erro
- **Segurança** — chave secreta fora do código, modo debug desligado por padrão, proteção contra HTML/script injetado em títulos, descrições e comentários

## Tecnologias utilizadas

- Python 3
- Flask
- Flask-SQLAlchemy
- SQLite
- JavaScript (fetch) para as atualizações sem recarregar
- Tailwind CSS (via CDN)

## Como rodar o projeto localmente

1. Clone o repositório:
   ```
   git clone https://github.com/Guizerasz/projeto-streaming-ac1.git
   cd projeto-streaming-ac1
   ```

2. (Recomendado) Crie um ambiente virtual:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

3. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

4. Rode a aplicação:
   ```
   python app.py
   ```

5. Acesse no navegador: http://127.0.0.1:5000

### Configurações opcionais

- **SECRET_KEY** — se a variável de ambiente não existir, o app cria sozinho a chave em `instance/secret_key.txt` (ignorada pelo git).
- **FLASK_DEBUG=1** — liga o modo debug, só para desenvolvimento (por padrão fica desligado).

## Estrutura do projeto

```
projeto_streaming/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── templates/
│   ├── _cabecalho.html        (partes reaproveitadas)
│   ├── _card_video.html
│   ├── _mensagens.html
│   ├── login.html
│   ├── cadastro.html
│   ├── painel.html
│   ├── perfil.html
│   ├── cadastro_video.html
│   ├── editar_video.html
│   ├── video.html
│   └── erro.html
├── static/
│   └── videos/                (vídeos enviados, ignorados pelo git)
├── docs/
│   └── diagramas/             (diagrama de classes e de casos de uso)
└── instance/                  (banco e chave secreta, gerados e ignorados pelo git)
```

## Diagramas

- [Diagrama de classes](docs/diagramas/diagrama_de_classes.png)
- [Diagrama de casos de uso](docs/diagramas/diagrama_de_casos_de_uso.png)

## Melhorias futuras

- Busca de vídeos e categorias
- Trocar o arquivo de um vídeo já enviado
- Foto de perfil
