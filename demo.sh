#!/bin/bash
# Roteiro de demonstração do agendamento-api (vídeo do AT).
# Pré-requisito: servidor no ar em http://127.0.0.1:8000 (de preferência com banco limpo).
#   rm -f agendamento.db && ./venv/bin/python -m uvicorn app.main:app        # macOS e Linux
#   rm -f agendamento.db && ./venv/Scripts/python.exe -m uvicorn app.main:app # Windows (Git Bash)
# Uso: ./demo.sh   (aperte Enter para avançar cada cenário)

B=http://127.0.0.1:8000
# O venv guarda os executaveis em bin/ no macOS e Linux, e em Scripts/ no Windows (Git Bash).
PY=./venv/bin/python
[ -x "$PY" ] || PY=./venv/Scripts/python.exe
ADMIN_PW=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)
LAB_SECRET=$(grep '^LAB_CLIENT_SECRET=' .env | cut -d= -f2-)
json() { $PY -c "import sys,json;print(json.load(sys.stdin)$1)"; }

titulo() { printf "\n\033[1;36m========== %s ==========\033[0m\n" "$1"; }
cmd()    { printf "\033[0;33m$ %s\033[0m\n" "$1"; }
pausa()  { printf "\n\033[0;90m[Enter para o próximo]\033[0m"; read -r; }

titulo "0. Suíte de testes automatizados"
cmd "$PY -m pytest -q"
$PY -m pytest -q 2>&1 | tail -1
pausa

titulo "1. Cabeçalhos de segurança em toda resposta (Ex. 10)"
cmd "curl -sD - -o /dev/null $B/ | grep -iE 'strict-transport|x-frame|x-content|referrer|cache-control'"
curl -s -D - -o /dev/null $B/ | tr -d '\r' | grep -iE "strict-transport|x-frame|x-content|referrer|cache-control"
pausa

titulo "2. CORS com allowlist (Ex. 10)"
cmd "curl ... -H 'Origin: https://site-malicioso.com'   (origem NÃO autorizada)"
R=$(curl -s -D - -o /dev/null $B/ -H "Origin: https://site-malicioso.com" | tr -d '\r' | grep -i "access-control-allow-origin")
echo "${R:-(sem access-control-allow-origin — o navegador nega a leitura)}"
cmd "curl ... -H 'Origin: http://localhost:5173'        (origem autorizada)"
curl -s -D - -o /dev/null $B/ -H "Origin: http://localhost:5173" | tr -d '\r' | grep -i "access-control-allow-origin"
pausa

titulo "3. Login de administrador com MFA (Ex. 6)"
cmd "POST /token  (username=admin)"
R=$(curl -s -X POST $B/token -d username=admin --data-urlencode "password=$ADMIN_PW")
echo "$R" | $PY -c "import sys,json;d=json.load(sys.stdin);d['mfa_token']=d['mfa_token'][:10]+'...';print(json.dumps(d,ensure_ascii=False,indent=2))"
MT=$(echo "$R" | json "['mfa_token']"); CODE=$(echo "$R" | json "['codigo_simulado']")
cmd "POST /token/mfa  (confirma o código de 6 dígitos)"
ADMIN=$(curl -s -X POST $B/token/mfa -d "mfa_token=$MT" -d "codigo=$CODE" | json "['access_token']")
echo "→ token de administrador emitido (só após o 2º fator)"
pausa

titulo "4. Admin cadastra profissional e pacientes (Ex. 6)"
for u in "dra.ana|Dra. Ana Costa|profissional" "maria|Maria Souza|paciente" "joao|Joao Pereira|paciente"; do
  un=${u%%|*}; resto=${u#*|}; nm=${resto%|*}; pp=${resto##*|}
  cmd "POST /admin/usuarios  ($un / $pp)"
  curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST $B/admin/usuarios -H "Authorization: Bearer $ADMIN" \
    -H 'Content-Type: application/json' -d "{\"username\":\"$un\",\"nome\":\"$nm\",\"password\":\"senha-forte-123\",\"papel\":\"$pp\"}"
done
tok() { curl -s -X POST $B/token -d "username=$1" -d password=senha-forte-123 | json "['access_token']"; }
ANA=$(tok dra.ana); MARIA=$(tok maria); JOAO=$(tok joao)
pausa

titulo "5. response_model: a resposta só traz campos públicos (Ex. 2)"
D=$(date -v+7d +%Y-%m-%dT10:00:00 2>/dev/null || date -d "+7 days" +%Y-%m-%dT10:00:00)
cmd "POST /consultas  (dra.ana agenda para maria)"
C=$(curl -s -X POST $B/consultas -H "Authorization: Bearer $ANA" -H 'Content-Type: application/json' \
  -d "{\"paciente\":\"maria\",\"especialidade\":\"Cardiologia\",\"data_hora\":\"$D\",\"motivo\":\"Dor no peito\"}")
echo "$C" | $PY -c "import sys,json;print(json.dumps(json.load(sys.stdin),ensure_ascii=False,indent=2))"
CID=$(echo "$C" | json "['id']")
echo "→ note: sem prontuario_paciente, audit_token, paciente_id (filtrados pelo response_model)"
pausa

titulo "6. BOLA / ownership: paciente não lê consulta de outro (Ex. 6/9)"
cmd "GET /consultas/$CID  (como JOAO — não é a consulta dele)"
curl -s -w "  HTTP %{http_code}\n" $B/consultas/$CID -H "Authorization: Bearer $JOAO"
cmd "GET /consultas/99999  (id inexistente — MESMA resposta, não confirma existência)"
curl -s -w "  HTTP %{http_code}\n" $B/consultas/99999 -H "Authorization: Bearer $JOAO"
cmd "GET /consultas/$CID  (como MARIA — a dona)"
curl -s -o /dev/null -w "  HTTP %{http_code} (200 OK)\n" $B/consultas/$CID -H "Authorization: Bearer $MARIA"
pausa

titulo "7. BFLA / escopo: paciente não acessa rota de admin (Ex. 6)"
cmd "GET /admin/usuarios  (como MARIA, paciente)"
curl -s -w "  HTTP %{http_code}\n" $B/admin/usuarios -H "Authorization: Bearer $MARIA"
cmd "POST /consultas  (paciente tentando escrever)"
curl -s -o /dev/null -w "  HTTP %{http_code} (403 Forbidden)\n" -X POST $B/consultas -H "Authorization: Bearer $MARIA" \
  -H 'Content-Type: application/json' -d "{\"paciente\":\"maria\",\"especialidade\":\"x\",\"data_hora\":\"$D\",\"motivo\":\"x\"}"
pausa

titulo "8. SQL Injection bloqueada na busca (Ex. 8/9/11)"
curl -s -o /dev/null -X POST $B/consultas/$CID/prontuario -H "Authorization: Bearer $ANA" -H 'Content-Type: application/json' \
  -d '{"diagnostico":"Angina estavel","anotacoes":"Dor aos esforcos."}'
cmd "GET /prontuarios/busca?termo=Angina   (busca legítima)"
curl -s -G $B/prontuarios/busca --data-urlencode "termo=Angina" -H "Authorization: Bearer $MARIA" \
  | $PY -c "import sys,json;print('  diagnosticos:',[p['diagnostico'] for p in json.load(sys.stdin)])"
cmd "GET /prontuarios/busca?termo=' OR 1=1 --   (payload de injeção)"
curl -s -o /dev/null -w "  HTTP %{http_code} (422 — barrado na whitelist, antes de tocar no banco)\n" \
  -G $B/prontuarios/busca --data-urlencode "termo=' OR 1=1 --" -H "Authorization: Bearer $MARIA"
pausa

titulo "9. Laboratório M2M: escopo isolado por contrato (Ex. 7)"
cmd "POST /token/m2m  (client credentials)"
LAB=$(curl -s -X POST $B/token/m2m -d grant_type=client_credentials -d client_id=laboratorio-parceiro \
  --data-urlencode "client_secret=$LAB_SECRET" | json "['access_token']")
$PY -c "import jwt,json;print('  claims:',json.dumps(jwt.decode('$LAB',options={'verify_signature':False})))"
cmd "GET /laboratorio/pedidos  (dentro do contrato)"
curl -s -o /dev/null -w "  HTTP %{http_code} (200 OK)\n" $B/laboratorio/pedidos -H "Authorization: Bearer $LAB"
cmd "GET /consultas  (FORA do contrato — token do laboratório)"
curl -s -w "  HTTP %{http_code}\n" $B/consultas -H "Authorization: Bearer $LAB"
pausa

titulo "10. Rate limiting no login contra brute force (Ex. 10)"
cmd "8 tentativas de login seguidas com senha errada"
printf "  "
for i in $(seq 1 8); do curl -s -o /dev/null -w "%{http_code} " -X POST $B/token -d username=maria -d password=errada; done
echo ""
echo "  Limite: 5 tentativas/min por IP. O limitador conta TODAS as tentativas do IP"
echo "  (inclusive os logins já feitos nesta demo), por isso o 429 aparece cedo."

printf "\n\033[1;32m===== Fim da demonstração =====\033[0m\n"
