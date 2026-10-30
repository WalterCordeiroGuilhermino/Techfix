-- =====================================================================
-- TechFix Informática — Sistema de Ordens de Serviço
-- Script de criação do banco (Supabase / PostgreSQL)
--
-- Como usar: cole este arquivo inteiro no SQL Editor do Supabase e
-- clique em "Run". O script pode ser executado mais de uma vez sem erro
-- (usa IF NOT EXISTS / DROP ... IF EXISTS onde necessário).
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. TABELA DE CLIENTES
-- Um cliente é identificado de forma única pelo e-mail. O mesmo cliente
-- pode abrir várias ordens de serviço ao longo do tempo (relação 1:N).
-- ---------------------------------------------------------------------
create table if not exists public.clientes (
  -- Chave primária gerada automaticamente pelo banco
  id               bigint generated always as identity primary key,

  -- Dados obrigatórios do cliente
  nome             text not null,
  endereco         text not null,
  email            text not null,
  celular_whatsapp text not null,

  -- Data de cadastro preenchida automaticamente com o momento atual
  data_cadastro    timestamptz not null default now(),

  -- Restrição UNIQUE: não podem existir dois clientes com o mesmo e-mail
  constraint clientes_email_unico unique (email),

  -- Nome e endereço não podem ser só espaços em branco
  constraint clientes_nome_preenchido     check (length(trim(nome)) > 0),
  constraint clientes_endereco_preenchido check (length(trim(endereco)) > 0),

  -- Validação simples do formato do e-mail (algo@dominio.ext)
  constraint clientes_email_formato
    check (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),

  -- Celular: somente dígitos, de 10 a 13 caracteres (ex.: 19999998888)
  constraint clientes_celular_formato
    check (celular_whatsapp ~ '^[0-9]{10,13}$')
);

comment on table public.clientes is 'Clientes da TechFix Informática';


-- ---------------------------------------------------------------------
-- 2. TABELA DE ORDENS DE SERVIÇO
-- Cada OS pertence a um cliente (chave estrangeira cliente_id).
-- ON DELETE CASCADE: ao excluir um cliente, as OS dele são excluídas
-- junto, evitando ordens "órfãs" sem cliente.
-- ---------------------------------------------------------------------
create table if not exists public.ordens_servico (
  -- Chave primária (é o "número da OS" mostrado ao cliente)
  id                bigint generated always as identity primary key,

  -- Chave estrangeira para clientes, com comportamento de exclusão definido
  cliente_id        bigint not null
                    references public.clientes (id)
                    on update cascade
                    on delete cascade,

  -- Dados do equipamento e do defeito
  modelo_computador text not null,
  problema_relatado text not null,

  -- Status do atendimento; toda OS nasce como 'Aberto'
  status            text not null default 'Aberto',

  -- Datas de controle
  data_abertura     timestamptz not null default now(),
  data_atualizacao  timestamptz not null default now(),

  -- Campos de texto não podem ficar vazios
  constraint os_modelo_preenchido   check (length(trim(modelo_computador)) > 0),
  constraint os_problema_preenchido check (length(trim(problema_relatado)) > 0),

  -- Restrição CHECK: só aceita os status definidos pela loja
  constraint os_status_valido check (
    status in ('Aberto', 'Em análise', 'Aguardando peça', 'Concluído', 'Entregue')
  )
);

comment on table public.ordens_servico is 'Ordens de serviço (equipamentos deixados para reparo)';


-- ---------------------------------------------------------------------
-- 3. ÍNDICES
-- Aceleram as consultas mais comuns do painel: OS de um cliente e
-- filtro por status. (O UNIQUE do e-mail já cria um índice sozinho.)
-- ---------------------------------------------------------------------
create index if not exists idx_os_cliente_id on public.ordens_servico (cliente_id);
create index if not exists idx_os_status     on public.ordens_servico (status);


-- ---------------------------------------------------------------------
-- 4. ATUALIZAÇÃO AUTOMÁTICA DE data_atualizacao
-- Sempre que uma OS for alterada (ex.: mudança de status), o trigger
-- grava o horário da alteração, sem depender da aplicação.
-- ---------------------------------------------------------------------
create or replace function public.atualizar_data_atualizacao()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.data_atualizacao := now();
  return new;
end;
$$;

drop trigger if exists trg_os_data_atualizacao on public.ordens_servico;
create trigger trg_os_data_atualizacao
  before update on public.ordens_servico
  for each row
  execute function public.atualizar_data_atualizacao();


-- ---------------------------------------------------------------------
-- 5. SEGURANÇA — ROW LEVEL SECURITY (RLS)
-- Com o RLS ligado, ninguém acessa as tabelas sem uma política explícita.
--
-- * App Gradio (balcão) usa a chave ANON: só pode CONSULTAR e INSERIR
--   (precisa consultar para reaproveitar o cliente pelo e-mail).
--   Não pode editar nem excluir nada.
-- * Painel Streamlit (gerente) usa a chave SERVICE_ROLE, que ignora o
--   RLS e tem acesso total. Essa chave fica só no secrets.toml do
--   servidor e nunca vai para o código nem para o GitHub.
-- ---------------------------------------------------------------------
alter table public.clientes       enable row level security;
alter table public.ordens_servico enable row level security;

-- Clientes: atendimento pode consultar e cadastrar
drop policy if exists "atendimento_consulta_clientes" on public.clientes;
create policy "atendimento_consulta_clientes"
  on public.clientes for select to anon
  using (true);

drop policy if exists "atendimento_cadastra_clientes" on public.clientes;
create policy "atendimento_cadastra_clientes"
  on public.clientes for insert to anon
  with check (true);

-- Ordens de serviço: atendimento pode abrir OS, mas sempre com status 'Aberto'
drop policy if exists "atendimento_consulta_os" on public.ordens_servico;
create policy "atendimento_consulta_os"
  on public.ordens_servico for select to anon
  using (true);

drop policy if exists "atendimento_abre_os" on public.ordens_servico;
create policy "atendimento_abre_os"
  on public.ordens_servico for insert to anon
  with check (status = 'Aberto');


-- ---------------------------------------------------------------------
-- 6. PERMISSÕES (GRANTS)
-- Garante que os papéis do Supabase enxerguem as tabelas pela API.
-- ---------------------------------------------------------------------
grant usage on schema public to anon, service_role;

grant select, insert on public.clientes, public.ordens_servico to anon;
grant all            on public.clientes, public.ordens_servico to service_role;

grant usage, select on all sequences in schema public to anon, service_role;


-- ---------------------------------------------------------------------
-- 7. DADOS DE TESTE (OPCIONAL — somente dados fictícios, LGPD)
-- Descomente e execute UMA vez para popular o banco e testar o painel.
-- ---------------------------------------------------------------------
-- insert into public.clientes (nome, endereco, email, celular_whatsapp) values
--   ('Walter Cordeiro Guilhermino',    'Rua Perpetua, 000 - Hortolandia', 'walter@exemplo.com',    '19900000001'),
-- on conflict (email) do nothing;
--
-- insert into public.ordens_servico (cliente_id, modelo_computador, problema_relatado, status)
-- select id, 'Notebook Dell Inspiron 15', 'Não liga, LED de energia apagado', 'Aberto'
--   from public.clientes where email = 'walter@exemplo.com'
-- union all
-- select id, 'Desktop Positivo', 'Muito lento, suspeita de vírus', 'Em análise'
--   from public.clientes where email = 'walter@exemplo.com'
-- union all
-- select id, 'Notebook Lenovo IdeaPad', 'Tela quebrada', 'Aguardando peça'
--   from public.clientes where email = 'walter@exemplo.com'
-- union all
-- select id, 'Impressora HP DeskJet', 'Não puxa papel', 'Concluído'
--   from public.clientes where email = 'walter@exemplo.com';
