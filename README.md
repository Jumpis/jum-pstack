# jum-pstack

Lauren Tan의 [pstack](https://github.com/cursor/plugins/tree/main/pstack)을 Claude Code, Codex, Hermes에서 쓰도록 묶은 배포판입니다. 매주 upstream을 따라가고, upstream 파일은 고치지 않습니다.

- **스킬 내용**은 upstream 그대로입니다. upstream이 Claude Code용으로 만든 트리(`harness/pstack/claude-code`)를 가져옵니다.
- **런타임 차이**는 어댑터 문서가 맡습니다. 스킬은 Cursor 이름(`Task`, `AskQuestion` 등)을 쓰고, 각 런타임은 자기 어댑터(`docs/harness/claude-code.md`, `codex.md`, `hermes.md`)로 이름을 바꿔 읽습니다. Claude Code 어댑터는 upstream 것이고, Codex·Hermes 어댑터는 이 저장소가 더합니다.
- **세션 시작 훅**(Claude Code, Codex)이 어댑터 위치와 `poteto-mode`로 보낼 작업을 알려 줍니다. 끄려면 `JUM_PSTACK_ROUTING=off`.

## 설치

### Claude Code

```text
/plugin marketplace add Jumpis/jum-pstack
/plugin install pstack@jum-pstack
```

서드파티 마켓플레이스는 자동 업데이트가 꺼져 있습니다. `/plugin` → Marketplaces → `jum-pstack` → Enable auto-update를 켜면 주간 갱신이 자동으로 들어옵니다. 다른 경로로 설치한 pstack(`pstack@cursor-plugins`, `pstack@pstack-claude`)이 있으면 지우세요. 스킬 이름이 겹칩니다.

### Codex

```sh
codex plugin marketplace add Jumpis/jum-pstack
codex plugin add pstack@jum-pstack
```

- 세션 시작 훅은 `/hooks`에서 신뢰해야 동작합니다.
- 서브에이전트를 쓰는 스킬(arena, interrogate 등)에는 `~/.codex/config.toml`의 `[features]`에 `multi_agent = true`가 필요합니다.
- 갱신: `codex plugin marketplace upgrade jum-pstack`
- 스킬은 `$pstack:poteto-mode`처럼 부릅니다.

### Hermes

```sh
git clone https://github.com/Jumpis/jum-pstack ~/jum-pstack
```

`~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - ~/jum-pstack/plugins/pstack/skills
    - ~/jum-pstack/hermes/skills
  auto_load:
    - pstack-router
```

갱신은 `git -C ~/jum-pstack pull --ff-only`입니다. Hermes는 쓰기 가능한 외부 디렉터리의 스킬도 고칠 수 있어서, Hermes가 pstack 파일을 고쳤다면 pull이 멈추고 그 파일을 알려 줍니다. Hermes가 새로 만드는 스킬은 `skills.create_dir`로 이 클론 밖에 두세요.

## 동기화

Claude 루틴이 매주 월요일 08:10(KST)에 [CLAUDE.md](CLAUDE.md)의 절차대로 upstream을 확인합니다. 바뀌었으면 동기화, 빌드, 검사를 거쳐 머지하고, 바뀌지 않았으면 아무것도 하지 않습니다.

```sh
python3 tools/jp.py sync    # upstream 트리를 vendor/pstack으로, VERSION 올림
python3 tools/jp.py build   # vendor + overlay → plugins/pstack, 마켓플레이스 카탈로그
python3 tools/jp.py check   # 빌드 최신 여부, 어댑터가 upstream 항목을 모두 다루는지, 버전, 훅
```

| 경로 | 내용 |
| --- | --- |
| `vendor/pstack/` | upstream 사본. sync만 씁니다. |
| `overlay/` | Codex·Hermes 어댑터, 세션 시작 훅, 내 스킬 |
| `plugins/pstack/` | 설치 대상. build가 만듭니다. |
| `hermes/skills/` | Hermes 라우터 스킬 |

## 라이선스

pstack은 Lauren Tan의 MIT 라이선스입니다(`vendor/pstack/LICENSE`). 이 저장소가 더한 부분도 MIT입니다([LICENSE](LICENSE), [NOTICE.md](NOTICE.md)).
