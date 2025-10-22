// Importar Express.js const express = require ( 'express' );


// Crie um aplicativo Express const app = express ();


// Middleware para analisar corpos JSON 
app . use ( express . json ());

// Definir porta e verify_token const port = process . env . PORT || 3000 ; const verifyToken = process . env . VERIFY_TOKEN ;
 


// Rota para solicitações GET 
app . get ( '/' , ( req , res ) => { const { 'hub.mode' : mode , 'hub.challenge' : challenge , 'hub.verify_token' : token } = req . query ;   
       

  se ( modo === 'inscrever-se' && token === verifyToken ) { 
    console . log ( 'WEBHOOK VERIFICADO' ); 
    res . status ( 200 ). enviar ( desafio ); } senão { 
    res . status ( 403 ). fim (); } });    
    
  


// Rota para solicitações POST 
app . post ( '/' , ( req , res ) => { const timestamp = new Date (). toISOString (). replace ( 'T' , ' ' ). slice ( 0 , 19 ); 
  console . log (` \n\n Webhook recebido $ { timestamp } \n `); 
  console . log ( JSON . stringify ( req . body , null , 2 )); 
  res . status ( 200 ). end (); });   
        


// Inicie o aplicativo do servidor . 
listen ( port , ( ) = > { 
  console.log (` \n Escutando na porta $ { port } \n` ); });
