# StreamHub — Plataforma de Streaming (Projeto Acadêmico)

Aplicação web de autenticação (cadastro e login) para uma plataforma de streaming fictícia, desenvolvida em Python com Flask.

## Funcionalidades

- Cadastro de novos usuários
- Login com verificação de credenciais
- Armazenamento seguro de senhas (hash via Werkzeug, não texto puro)
- Painel inicial exibido após o login

## Tecnologias utilizadas

- Python 3
- Flask
- Flask-SQLAlchemy
- SQLite
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
│   └── painel.html
└── instance/
    └── database.db   (gerado automaticamente, ignorado pelo git)
```

## Melhorias futuras

- Sessão de login persistente (Flask session)
- Painel de usuário completo
- Validação adicional de formulários no backend

## Autor

Guilherme
