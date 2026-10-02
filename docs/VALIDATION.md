# Validação da revisão 1.1.0

Validação realizada em 2 de outubro de 2026, no ambiente Linux da tarefa, com Python 3.12.14, PySide6 6.11.2, VLC 3.0.23 e FFmpeg. Este registro descreve testes locais; não equivale a uma validação na câmera da igreja.

## Resultados

- **49 testes passaram**, sem testes desativados, esperados como falha ou ignorados. Os 22 testes originais passaram antes das alterações. A verificação antiga que fazia teclas expirarem após 350 ms foi substituída por um teste de tecla mantida e soltura, pois o atraso inicial de repetição do sistema podia provocar paradas indevidas.
- Comunicação HTTP autenticada em loopback, escrita e leitura de confirmação de imagem, rejeição de senha incorreta, preservação de campos desconhecidos e bloqueio de escrita após uma leitura que falhou.
- Tráfego UDP VISCA em loopback, consulta de posição, descarte de resposta com sequência antiga e bytes das quatro diagonais.
- Aceleração, inversão e parada para três curvas e três posições de zoom. Limite de velocidade aplicado também ao teclado. Retransmissões atrasadas de parada não interrompem comandos novos.
- Fluxo da aplicação completa: abertura, conexão ao simulador, alteração de brilho, comando diagonal, parada, desconexão e encerramento da thread de rede.
- Abertura da interface mesmo sem VLC, alternância de tema e geração de captura da interface.
- Entrada USB/Bluetooth com backend simulado: posição neutra obrigatória, botão de emergência, perda de foco e remoção de dispositivo. Nenhum controle físico foi conectado ao ambiente.
- Reprodução e captura de vídeo sintético com VLC e apresentação de frames em Qt, sem depender de uma janela nativa de vídeo.
- **RTSP real em loopback** com MediaMTX 1.12.3 e fonte H.264 gerada por FFmpeg: prévia decodificada de 1280×720, PNG válido e gravação MKV confirmada por `ffprobe` como H.264 de 640×360. A fonte de teste era 640×360; isso não mede uma transmissão real de 1080p. A verificação final por `scripts/check-video.py` gravou 3,8 segundos.
- `scripts/setup-cloud.sh` executado e repetido no mesmo ambiente; dependências já preparadas reutilizadas e testes passaram. Não foi validada restauração em uma nova tarefa.

## Limites e próximos testes

A câmera da igreja é chinesa white label, sem marca/modelo conhecidos. O ambiente de nuvem não alcança sua rede local. Ainda precisam de validação no equipamento: autenticação real, layout de `VideoParam`, códigos e limites de exposição/balanço de branco, suporte aos comandos HTTP, faixa óptica VISCA, presets e resposta física aos movimentos. A descoberta por multicast e a entrada física também exigem uma rede/dispositivo reais.

Os campos de imagem agora dependem de uma resposta compatível e da confirmação de leitura. Eles podem ficar indisponíveis em firmware diferente; isso é informado pela interface. O aplicativo não promete compatibilidade universal com câmeras ONVIF.

Na rede da igreja, use primeiro a menor velocidade, confira parada e diagonais, teste wide/tele e só então ative compensação de zoom se a faixa for compatível. Leia os ajustes antes de alterar um campo. Para investigar o firmware, exporte o diagnóstico pelo menu Câmera; ele omite credenciais e URLs de stream.

Não foram gerados instaladores Windows/macOS nem executados testes nesses sistemas. O projeto inclui instruções de instalação e código de plataforma portátil; a publicação do código não substitui esses testes.
