# Arquitetura e regras da V1

Frontend React → Nginx `/api` → FastAPI → PostgreSQL. Base de dados e autenticação próprias; nenhuma chamada à Unidal. JWT com duração de 8 horas, guardado em sessionStorage; contas inativas deixam de ter acesso imediatamente porque a API consulta o utilizador em cada chamada. Senhas PBKDF2-SHA256 com salt individual e 600 mil iterações.

## Perfis

| Operação | Bombista | Administrador |
| --- | --- | --- |
| Criar apontamento próprio | Sim | Sim |
| Ver apontamentos | Próprios | Todos |
| Editar rascunho/devolvido | Próprios | Todos |
| Editar submetido | Não | Sim, com histórico |
| Editar aprovado | Não | Não |
| Aprovar/devolver | Não | Sim |
| Relatórios e histórico | Não | Sim |
| Gerir cadastros/utilizadores | Não | Sim |

## Entidades

`users` guarda contas. `catalog` guarda clientes, obras, bombas e ajudantes; apenas obras possuem cliente associado. `entries` guarda serviço, equipa e medidas. `audit` guarda autor, data e ação; edições incluem os valores anteriores. Alembic controla versões do esquema.

## Deslocamentos

Origem e destino representam a bomba/equipa. Um serviço na obra A pode ter origem no estaleiro e destino na obra B. Um serviço seguinte na obra B pode ter origem na obra A e destino no estaleiro. Não há sugestão automática nesta V1. Se forem introduzidas horas/km de deslocamento, cada trajeto A → B deve existir uma única vez para evitar duplicação entre os dois serviços.

## Horas e integridade

Horários possuem data e fuso, são convertidos para UTC e exibidos no fuso do dispositivo. Serviços que atravessam a meia-noite usam a data seguinte no fim. O filtro de período seleciona pelo início do serviço; não divide serviços entre dois dias. Horas = diferença fim/início menos pausa, arredondada a duas casas por serviço. Pausa inteira em minutos, inferior à duração. Volume e linha admitem zero e até duas casas decimais.

Sobreposição usa intervalos abertos no fim: um serviço pode iniciar exatamente quando o anterior termina. Pausas não libertam a equipa para outro serviço. No PostgreSQL, a gravação verifica sobreposições sob advisory lock transacional; revisão do apontamento usa lock de linha e número de versão para impedir edição com formulário desatualizado.

Obra com apontamentos não pode trocar de cliente. Cadastros inativos não podem ser selecionados em novos apontamentos ou correções. Relatórios só incluem aprovados. A soma dos metros de linha representa montagens por serviço, não inventário de tubos. As horas reportadas são horas de serviço do bombista; não somam o ajudante como horas adicionais.

## Evolução

Próximos incrementos: horários/km de deslocamento, participantes com períodos próprios, nomes preservados por serviço, filtros/paginação na lista, redefinição de senha, PWA/offline, assinatura do cliente e exportação XLSX. Cada alteração de esquema deve ter uma migration nova, sem modificar a migration já aplicada.
