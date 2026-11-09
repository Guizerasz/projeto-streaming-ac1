# StreamHub — Plataforma de Streaming (Projeto Acadêmico)

Plataforma de streaming fictícia desenvolvida em Python com Flask. Os usuários criam conta, publicam vídeos (por link do YouTube ou enviando um arquivo) e interagem com eles por curtidas e comentários.

## Funcionalidades

**Usuários (AC1)**
- Cadastro de novos usuários, com aviso quando o nome já existe
- Login com sessão (o sistema sabe quem está logado) e logout
- Senhas armazenadas com hash (Werkzeug), nunca em texto puro

**Vídeos (AC2)**
- Cadastro de vídeo com título, descrição e link do YouTube ou arquivo enviado do computador (.mp4, .webm, .ogg, .mov)
- Reconhecimento automático de links do YouTube, com player embutido
- Listagem dos vídeos no painel, do mais novo para o mais antigo

**Interação (AC3)**
- Página própria para cada vídeo
- Curtir e descurtir (uma curtida por usuário em cada vídeo)
- Comentários de até 300 caracteres, com autor e data
- Atualização sem recarregar a página: o que a própria pessoa faz aparece na hora, e curtidas e comentários de outras pessoas aparecem sozinhos em poucos segundos
- Total de curtidas e comentários em cada card do painel

## Tecnologias utilizadas

- Python 3
- Flask
- Flask-SQLAlchemy
- SQLite
- JavaScript (fetch) para as atualizações em tempo real
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

## Estrutura do projeto

```
projeto_streaming/
├── app.py
├── requirements.txt
├── .gitignore
├── templates/
│   ├── login.html
│   ├── cadastro.html
│   ├── painel.html
│   ├── cadastro_video.html
│   └── video.html
├── static/
│   └── videos/           (vídeos enviados, ignorados pelo git)
└── instance/
    └── database.db       (gerado automaticamente, ignorado pelo git)
```

## Melhorias futuras

- Editar e excluir vídeos cadastrados
- Excluir os próprios comentários
- Validação adicional de formulários no backend
