import { useState } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');

  const handleSend = (e) => {
    e.preventDefault();
    if (inputText.trim() === '') return;

    const userMessage = {
      id: self.crypto.randomUUID(),
      text: inputText,
      sender: 'user',
    };

    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setInputText('');

    // Simulate bot response
    setTimeout(() => {
      const botMessage = {
        id: self.crypto.randomUUID(),
        text: 'Ceci est une réponse simulée.',
        sender: 'bot',
      };
      setMessages((prevMessages) => [...prevMessages, botMessage]);
    }, 1000);
  };

  return (
    <div className="chat-container">
      <div className="message-list">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`message ${message.sender === 'user' ? 'user-message' : 'bot-message'}`}
          >
            {message.text}
          </div>
        ))}
      </div>
      <form className="input-form" onSubmit={handleSend}>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Écrivez un message..."
        />
        <button type="submit">Envoyer</button>
      </form>
    </div>
  );
}

export default App;