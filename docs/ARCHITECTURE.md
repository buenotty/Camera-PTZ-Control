# Arquitetura

`src/app.py` conecta os componentes de interface, entrada e comunicação. A janela não implementa comandos de hardware.

- **MotionEngine:** normaliza entradas, aplica um limite de velocidade comum a teclado/mouse/joystick e interpola cada eixo a partir de uma origem fixa. A curva não é reaplicada ao resultado do frame anterior. Zeros e inversões são enviados mesmo quando a mudança de velocidade é pequena.
- **CameraManager:** seleciona o transporte disponível, invalida retransmissões de parada quando um novo movimento começa e coordena o worker de rede. HTTP usa uma caixa de mensagens que mantém a intenção mais recente por eixo, evitando uma fila de movimentos obsoletos. `Stop` HTTP é global; o worker reenvia eixos que devem continuar ativos.
- **VISCAClient:** associa respostas à sequência e ao endereço de origem. Abrir o socket não prova conectividade; uma consulta de zoom deve receber resposta. O suporte atual exige o envelope VISCA over IP de oito bytes, não VISCA serial ou UDP sem envelope.
- **BolinAPIClient / image_protocol:** reutilizam o formato autenticado da aplicação original. O suporte é determinado pela resposta `VideoParam`; campos desconhecidos são preservados. Escritas de imagem são comparadas com uma leitura subsequente, e uma leitura que falhou não permite escrever um cache antigo. Os códigos de exposição/balanço são específicos da família implementada.
- **VideoPanel:** apresenta frames como imagens Qt, evitando problemas de janela nativa e sobreposição. RTSP prefere FFmpeg quando disponível. VLC usa callbacks de memória como alternativa. Uma única notificação pendente apresenta o frame mais recente, sem acumular frames na UI.
- **GamepadHandler:** entrada física opcional via pygame-ce, com zona morta e exigência de posição neutra depois de uma parada. O estado físico precisa ser validado com um dispositivo real; testes usam um backend simulado.

A reprodução RTSP, o controle PTZ e os ajustes de sensor são capacidades separadas. Uma imagem visível não prova suporte à API de imagem; descobrir uma câmera via ONVIF não prova suporte VISCA ou Bolin.

Credenciais não são serializadas em perfis ou preferências. Chamadas HTTP e decodificação ficam fora da thread de interface. Erros não incluem corpos de requisição ou URLs de stream com credenciais.
