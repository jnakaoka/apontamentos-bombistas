# Apontamentos de Bombistas — V1

Sistema independente da Unidal. FastAPI + SQLAlchemy + Alembic + PostgreSQL, React + Vite e Docker Compose. Interface responsiva para telemóvel e computador.

## Incluído

- Login e perfis administrador/bombista, com autorização na API.
- Bombista consulta apenas os próprios serviços; administrador consulta todos.
- Clientes, obras vinculadas ao cliente, bombas e ajudantes (sem login próprio).
- Vários serviços no mesmo dia: um apontamento por serviço/obra.
- Início/fim do trabalho, pausa em minutos, horas calculadas, m³ de betão, metros de linha, origem/destino da bomba/equipa e observações.
- Rascunho → submissão → aprovação ou devolução para correção.
- Apontamentos aprovados bloqueados para edição; histórico de alterações disponível ao administrador.
- Bloqueio de sobreposição de horários para o mesmo bombista, bomba ou ajudante.
- Relatórios de serviços aprovados, com período/bombista/cliente/obra/bomba e exportação CSV compatível com Excel.
- Cadastros e utilizadores podem ser desativados sem apagar apontamentos existentes.

## Executar no Windows, Linux ou servidor com Docker

```bash
git clone https://github.com/jnakaoka/apontamentos-bombistas.git
cd apontamentos-bombistas
cp .env.example .env
```

No PowerShell, use `Copy-Item .env.example .env`. Edite `.env` antes de iniciar: escolha ADMIN_EMAIL e ADMIN_PASSWORD; substitua JWT_SECRET e DB_PASSWORD por valores aleatórios diferentes. Não publique o `.env`. Para a senha do PostgreSQL, use caracteres alfanuméricos/hexadecimais porque ela integra a URL de conexão.

```bash
docker compose up -d --build
docker compose logs -f api
```

Aceda a http://localhost:8085 e entre com os dados ADMIN_EMAIL/ADMIN_PASSWORD. O administrador inicial só é criado quando ainda não existem utilizadores. Alterar essas variáveis depois não altera a conta existente.

O administrador pode criar e desativar utilizadores; o registo público não existe. Cada utilizador altera a própria senha em **Minha conta**; o administrador pode redefinir a senha de outra conta. Uma alteração ou redefinição revoga imediatamente os tokens anteriores. Não partilhe senhas iniciais por canais inseguros.\n\nCadastre primeiro cliente, obra e bomba; depois ajudantes e contas de bombistas. Ajudante é opcional. Registe um serviço, guarde o rascunho e submeta. No perfil administrador, aprove ou devolva com motivo. Consulte o relatório após a aprovação.

Por segurança, a porta web está associada a `127.0.0.1` e não fica exposta diretamente à rede. Para testes no telemóvel, configure um proxy HTTPS ou altere temporariamente o binding apenas num ambiente de desenvolvimento confiável. A base de dados e a API não expõem portas próprias no Compose. O Nginx frontal da VPS deve fazer proxy para `127.0.0.1:8085`. Para acesso pela internet, configure domínio e HTTPS no proxy de entrada.

## Atualizar

```bash
git pull --ff-only
docker compose up -d --build
```

As migrations são aplicadas antes da API iniciar. O volume `db_data` mantém os dados. Não execute `docker compose down -v` para atualizar: esse comando apaga o volume da base de dados.

## Testes

```bash
cd backend
python -m pip install -r requirements.txt
python -m pip install pytest httpx
python -m pytest -q
```

Os testes usam SQLite temporário e verificam permissões, vários serviços, sobreposições, cálculo de horas, revisão, bloqueio de aprovados, exportação e contas inativas.

```bash
cd frontend
npm ci
npm run build
```

## Limites desta V1

- Origem/destino são locais em texto. Horas são do trabalho na obra, descontando pausas. Tempos/km de deslocamento ainda não são calculados.
- Não inclui offline/PWA instalável, fotos, assinatura, GPS, faturação ou recuperação de senha por email. O administrador pode redefinir senhas dos bombistas.
- Sem atribuição parcial de ajudante: o intervalo do serviço aplica-se à equipa toda.
- CSV é o formato de exportação; não é um ficheiro XLSX nativo.
- A primeira conta administrativa é criada pelo arranque; não há senha padrão funcional.
- Relatórios usam nomes atuais dos cadastros; o histórico guarda os valores anteriores nas edições de apontamentos.
- Esta é uma V1 para validação operacional. O Compose completo com PostgreSQL deve ser testado no ambiente de instalação antes de utilização real.

Detalhes das regras em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Preparação para produção

A branch `feature/preparacao-producao` contém melhorias de segurança em revisão. **Não declarar pronto para produção** antes de executar testes backend/frontend, validar PostgreSQL e migrations em Docker, verificar permissões, configurar HTTPS, backups e restauração e fazer testes end-to-end. O `ADMIN_PASSWORD` é apenas para o primeiro arranque de uma base vazia; altere a senha inicial pela interface. Mantenha o `.env` fora do controlo de versões. Configure o proxy externo e os cabeçalhos de segurança adequados.
