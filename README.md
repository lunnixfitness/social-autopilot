# social-autopilot — Instagram, Facebook, YouTube Shorts e LinkedIn no automático

Todo dia às **12:10 (Brasília)**, o GitHub Actions executa estas etapas:

1. Escolhe um tema do banco verificado (`autopilot/topics.yaml`). O rodízio é tributário → previdenciário → perícia → tributário → **Velatrix** (1 a cada 5), e nenhum tema se repete antes de o banco girar.
2. Gera a arte: carrossel 1080×1350, reel/Short 1080×1920 com movimento e transições, capa e story.
3. Se houver `GEMINI_API_KEY`, pede à IA uma versão nova da legenda. **A versão da IA é descartada** se trouxer número, lei, tema ou termo proibido que não esteja no banco.
4. Roda os testes. Se algum falhar, **nada é publicado** e o GitHub manda um e-mail.
5. Publica pelas **APIs oficiais**, com as hashtags no 1º comentário do Instagram.

| Dia | Instagram (feed) | Story | YouTube |
|---|---|---|---|
| Seg, Qua, Sex, Sáb | Reel | chamada para o post | Short (o mesmo vídeo) |
| Ter, Qui | Carrossel | chamada para o post | Short |
| Dom | nada | dica do dia | nada |

Para mudar o calendário, as cores, o CTA, o horário ou os termos proibidos, edite `autopilot/brand.yaml`. Para adicionar temas, edite `autopilot/topics.yaml` (sempre com a base legal).

### Travas (Provimento 205/2021 da OAB)
- Termos como "garantido", "causa ganha", "sem risco" e "100%" bloqueiam o post.
- Todo post leva a base legal e o aviso "Conteúdo informativo. Cada caso exige análise individual."
- Rodar o workflow de novo no mesmo dia não duplica post: o `state/history.json` registra o que já saiu em cada rede.

---

## Configuração (uma vez só)

### 1. GitHub Pages
Abra **Settings → Pages → Source** e escolha **GitHub Actions**. A mídia do dia fica pública ali para o Instagram buscar, e por isso o repositório precisa ser **público**. Os secrets continuam protegidos.

### 2. Instagram (API oficial, gratuita)
1. A conta precisa ser **Profissional** (Criador ou Empresa). Para publicar stories pela API, a Meta exige conta **Empresa**.
2. Em <https://developers.facebook.com/apps>, clique em **Criar app** e escolha o caso de uso **Gerenciar mensagens e conteúdo no Instagram**.
3. Abra **API do Instagram → Configuração da API com login do Instagram → Adicionar conta** e entre com @ademilson_melo2.0.
4. Confira as permissões `instagram_business_basic`, `instagram_business_content_publish` e `instagram_business_manage_comments`.
5. Clique em **Gerar token**. O token vale 60 dias, e o workflow `refresh-token` o renova sozinho nos dias 1 e 16.

Com o app em modo de desenvolvimento, a publicação já funciona na sua própria conta.

### 3. YouTube (API oficial, gratuita)
1. Em <https://console.cloud.google.com>, crie um projeto e ative a **YouTube Data API v3**.
2. Abra **APIs e serviços → Tela de consentimento OAuth**, escolha **Externo**, adicione o escopo `.../auth/youtube.upload` e clique em **Publicar app** (status **Em produção**). Em modo *Teste*, o token morre em 7 dias. O aviso de "app não verificado" aparece só para você e pode ser ignorado.
3. Abra **Credenciais → Criar ID do cliente OAuth → Aplicativo da Web** e, em URI de redirecionamento, coloque `https://developers.google.com/oauthplayground`.
4. Em <https://developers.google.com/oauthplayground>, clique na engrenagem, marque **Use your own OAuth credentials** e cole o Client ID e o Secret. No passo 1, digite `https://www.googleapis.com/auth/youtube.upload`, clique em **Authorize** e entre com a conta do canal. No passo 2, clique em **Exchange** e copie o **Refresh token**.

> ⚠️ **Trava do YouTube:** vídeos enviados por projetos de API que ainda não passaram na auditoria do Google ficam **privados**, por regra do YouTube, não por erro deste código. O workflow avisa no log quando isso acontece. Para liberar o modo público, preencha o formulário **YouTube API Services – Audit and Quota Extension**, que é gratuito e leva algumas semanas. Até a aprovação, os Shorts sobem e ficam prontos no YouTube Studio, e você pode publicar todos de uma vez lá, ou trocar `privacidade` para `private` no `brand.yaml` para assumir isso.

### 3.1 Facebook: Página Velatrix (API oficial, gratuita)
Reels e carrosséis do Instagram também saem na **Página Velatrix**: o reel vira Reel do Facebook, e o carrossel vira um post com várias fotos. Ao final de cada post vai o convite para o grupo (`brand.yaml → facebook.grupo_url`).
1. Use o mesmo app da Meta do passo 2 e adicione o produto **Facebook Login for Business**.
2. Em <https://developers.facebook.com/tools/explorer>, selecione o app e peça as permissões `pages_show_list`, `pages_manage_posts`, `pages_read_engagement` e `publish_video`. Gere o token de usuário.
3. No mesmo Explorer, consulte `me/accounts`: a linha da **Velatrix** traz o `id` (vai em `FB_PAGE_ID`) e o `access_token` da Página (vai em `FB_PAGE_TOKEN`). Se o token de usuário era de longa duração, o da Página não expira.

> **Grupos não têm API**: a Meta desligou a publicação em grupos em 2024. O grupo é tocado no app (posts agendados pelo próprio grupo), e o automático leva tráfego da Página, do Instagram e do YouTube para ele.

### 3.2 LinkedIn (API oficial, gratuita)
Terça, quarta e quinta às **08:30**, o workflow `linkedin` publica o próximo post da fila `content/linkedin/queue.yaml` no seu perfil e coloca o link no 1º comentário. Os posts vêm dos artigos do Blog Velatrix, com dado real e fonte oficial. As travas bloqueiam promessa de resultado, caso ou depoimento inventado e link no corpo do post.

1. Em <https://www.linkedin.com/developers/apps>, clique em **Create app** e vincule à Página **Velatrix**.
2. Na aba **Products**, adicione **Sign In with LinkedIn using OpenID Connect** e **Share on LinkedIn**.
3. Na aba **Auth**, em *Authorized redirect URLs*, cadastre `https://velatrix-blog.pages.dev/linkedin-retorno/`. Copie o **Client ID** e o **Client Secret** para os secrets `LINKEDIN_CLIENT_ID` e `LINKEDIN_CLIENT_SECRET`.
4. Abra no navegador (trocando `CLIENT_ID`):
   `https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=CLIENT_ID&redirect_uri=https%3A%2F%2Fvelatrix-blog.pages.dev%2Flinkedin-retorno%2F&scope=openid%20profile%20w_member_social&state=velatrix`
5. Autorize. A página de retorno mostra um código: copie e rode **Actions → linkedin-auth → Run workflow** colando o código (vale poucos minutos). O workflow grava `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN` e `LINKEDIN_TOKEN_CREATED_AT` usando o `GH_PAT`.
6. Teste com **Actions → linkedin → Run workflow** (dry_run marcado) e baixe o artefato `previa-linkedin`.

O token do LinkedIn vale **60 dias** e não renova sozinho. A partir do dia 50, o workflow abre a issue "Renovar token do LinkedIn": basta repetir os passos 4 e 5.

Para postar na **Página** Velatrix (e não só no perfil), o LinkedIn exige a *Community Management API*, que passa por revisão. Peça na aba Products quando quiser.

### 4. Secrets do repositório
Abra **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Obrigatório | O que é |
|---|---|---|
| `IG_ACCESS_TOKEN` | Instagram | o token do passo 2 |
| `GH_PAT` | Instagram | token *fine-grained* do GitHub, só deste repositório, com **Secrets: Read and write**. Renova o token do Instagram |
| `YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN` | YouTube | os valores do passo 3 |
| `FB_PAGE_ID` / `FB_PAGE_TOKEN` | Facebook | os valores do passo 3.1 |
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | LinkedIn | os valores do passo 3.2 (o token é gravado pelo workflow `linkedin-auth`) |
| `GEMINI_API_KEY` | não | chave do Google AI Studio. Sem ela, os textos saem como estão no banco |
| `IG_USER_ID` | não | descoberto automaticamente |

Cada rede funciona sozinha: sem os secrets dela, ela é pulada e a outra publica normalmente.

### 5. Suas fotos e música (recomendado)
- Envie de 3 a 8 fotos suas, em retrato e com boa luz, para `assets/fotos/`. Elas viram o fundo da capa do reel e dos stories, e rosto na capa aumenta o alcance.
- Se quiser música, coloque `.mp3` **livres de direitos** em `assets/audio/`, por exemplo da Biblioteca de Áudio do YouTube. Sem música, o vídeo sai com faixa silenciosa.

### 6. Narração por IA (Gemini TTS)
Com o secret `GEMINI_API_KEY` (chave grátis em <https://aistudio.google.com/apikey>), todo reel e Short sai com **locução em português**, lida a partir do texto verificado do banco. A voz, o tom e o liga/desliga ficam em `brand.yaml → voz`. A legenda e a descrição recebem o aviso "Narração com voz gerada por IA". Sem a chave, os vídeos saem só com música.

**Demos do Velatrix:** abra **Actions → demos → Run workflow**. Os 3 Shorts de demonstração são gerados com telas reais em `assets/demos/` e narração, e saem no artefato `demos` e na branch `demos-out`.

### 7. Teste
Abra **Actions → autopilot → Run workflow** com **dry_run** marcado e baixe o artefato `previa` para ver o que sairia. Quando estiver tudo certo, rode com o dry_run desmarcado ou espere as 12:10.

## O que continua sendo você
Responder comentários e DMs, fazer collabs e stories com figurinhas (enquete, caixinha, link). As APIs não fazem isso, e automatizar interação viola as regras das duas plataformas. Gravar 1 vídeo falando para a câmera por semana complementa muito bem o automático.

## Rodar localmente
```bash
pip install -r requirements.txt          # precisa de ffmpeg
python -m autopilot preview --days 7     # gera uma semana em preview/ sem publicar
python -m pytest -q tests
```
