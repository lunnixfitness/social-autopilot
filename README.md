# social-autopilot — Instagram + YouTube Shorts no automático

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

### 4. Secrets do repositório
Abra **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Obrigatório | O que é |
|---|---|---|
| `IG_ACCESS_TOKEN` | Instagram | o token do passo 2 |
| `GH_PAT` | Instagram | token *fine-grained* do GitHub, só deste repositório, com **Secrets: Read and write**. Renova o token do Instagram |
| `YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN` | YouTube | os valores do passo 3 |
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
