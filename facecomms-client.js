/**
 * FaceComms Real-time Communication Client
 * WebRTC + WebSocket for audio/video + chat
 */

class FaceCommsClient {
    constructor(wsUrl = 'ws://localhost:8765', config = {}) {
        this.wsUrl = wsUrl;
        this.ws = null;
        this.userId = config.userId || this.generateUserId();
        this.roomId = config.roomId || 'general';
        this.userName = config.userName || 'Anonymous';
        
        // WebRTC
        this.peerConnection = null;
        this.localStream = null;
        this.remoteStream = null;
        this.currentCallId = null;
        this.remotePeerId = null;
        
        // ICE servers
        this.iceServers = config.iceServers || [
            { urls: ['stun:stun.l.google.com:19302'] },
            { urls: ['stun:stun1.l.google.com:19302'] }
        ];
        
        // Callbacks
        this.callbacks = {
            onConnected: () => {},
            onChatMessage: () => {},
            onUserJoined: () => {},
            onUserLeft: () => {},
            onIncomingCall: () => {},
            onCallStarted: () => {},
            onCallEnded: () => {},
            onRemoteStream: () => {},
            onError: () => {}
        };
    }
    
    generateUserId() {
        return `user_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    async connect() {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(this.wsUrl);
            
            this.ws.onopen = () => {
                console.log('✓ WebSocket connected');
                this.authenticate();
                this.callbacks.onConnected();
                resolve();
            };
            
            this.ws.onmessage = (event) => this.handleMessage(JSON.parse(event.data));
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.callbacks.onError({ type: 'WS_ERROR', error });
                reject(error);
            };
            
            this.ws.onclose = () => {
                console.log('⊘ WebSocket disconnected');
                this.callbacks.onError({ type: 'WS_CLOSED' });
            };
        });
    }
    
    authenticate() {
        this.send({
            type: 'AUTH',
            user_id: this.userId,
            room_id: this.roomId
        });
    }
    
    async requestCall(targetUserId, targetUserName = 'User') {
        return new Promise((resolve) => {
            this.send({
                type: 'CALL_REQUEST',
                target_user_id: targetUserId,
                caller_name: this.userName
            });
            resolve();
        });
    }
    
    async acceptCall(callId, targetUserId) {
        this.currentCallId = callId;
        this.remotePeerId = targetUserId;
        
        this.send({
            type: 'CALL_ACCEPT',
            call_id: callId,
            acceptor_name: this.userName
        });
        
        await this.initializeWebRTC();
        await this.createOffer();
    }
    
    async rejectCall(callId, targetUserId) {
        this.send({
            type: 'CALL_REJECT',
            call_id: callId,
            target_user_id: targetUserId
        });
    }
    
    async endCall() {
        if (this.currentCallId && this.remotePeerId) {
            this.send({
                type: 'CALL_END',
                call_id: this.currentCallId,
                target_user_id: this.remotePeerId
            });
        }
        
        this.stopWebRTC();
        this.callbacks.onCallEnded();
    }
    
    async initializeWebRTC() {
        try {
            // Get local stream
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: { width: { ideal: 1280 }, height: { ideal: 720 } }
            });
            
            // Create peer connection
            this.peerConnection = new RTCPeerConnection({
                iceServers: this.iceServers
            });
            
            // Add local stream tracks
            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });
            
            // Handle remote stream
            this.peerConnection.ontrack = (event) => {
                this.remoteStream = event.streams[0];
                this.callbacks.onRemoteStream(this.remoteStream);
            };
            
            // Handle ICE candidates
            this.peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    this.send({
                        type: 'RTC_ICE_CANDIDATE',
                        target_user_id: this.remotePeerId,
                        candidate: event.candidate
                    });
                }
            };
            
            // Handle connection state changes
            this.peerConnection.onconnectionstatechange = () => {
                console.log('Connection state:', this.peerConnection.connectionState);
            };
            
        } catch (error) {
            console.error('WebRTC initialization error:', error);
            this.callbacks.onError({ type: 'WEBRTC_ERROR', error });
        }
    }
    
    async createOffer() {
        try {
            const offer = await this.peerConnection.createOffer();
            await this.peerConnection.setLocalDescription(offer);
            
            this.send({
                type: 'RTC_OFFER',
                target_user_id: this.remotePeerId,
                offer: offer
            });
        } catch (error) {
            console.error('Error creating offer:', error);
        }
    }
    
    async createAnswer() {
        try {
            const answer = await this.peerConnection.createAnswer();
            await this.peerConnection.setLocalDescription(answer);
            
            this.send({
                type: 'RTC_ANSWER',
                target_user_id: this.remotePeerId,
                answer: answer
            });
        } catch (error) {
            console.error('Error creating answer:', error);
        }
    }
    
    stopWebRTC() {
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
            this.localStream = null;
        }
        
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        
        this.remoteStream = null;
        this.currentCallId = null;
        this.remotePeerId = null;
    }
    
    sendChat(message) {
        this.send({
            type: 'CHAT',
            message: message
        });
    }
    
    async handleMessage(data) {
        const { type } = data;
        
        switch (type) {
            case 'AUTH_SUCCESS':
                console.log('✓ Authenticated:', data.user_id);
                break;
            
            case 'CHAT':
                this.callbacks.onChatMessage({
                    userId: data.user_id,
                    message: data.message,
                    timestamp: data.timestamp
                });
                break;
            
            case 'USER_JOINED':
                this.callbacks.onUserJoined(data.user_id);
                break;
            
            case 'USER_LEFT':
                this.callbacks.onUserLeft(data.user_id);
                break;
            
            case 'INCOMING_CALL':
                this.currentCallId = data.call_id;
                this.remotePeerId = data.caller_id;
                this.callbacks.onIncomingCall({
                    callId: data.call_id,
                    callerId: data.caller_id,
                    callerName: data.caller_name
                });
                break;
            
            case 'CALL_ACCEPTED':
                await this.initializeWebRTC();
                await this.createOffer();
                this.callbacks.onCallStarted({
                    callId: data.call_id,
                    acceptorId: data.acceptor_id
                });
                break;
            
            case 'RTC_OFFER':
                if (!this.peerConnection) await this.initializeWebRTC();
                await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
                await this.createAnswer();
                break;
            
            case 'RTC_ANSWER':
                await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.answer));
                break;
            
            case 'RTC_ICE_CANDIDATE':
                try {
                    await this.peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
                } catch (error) {
                    console.error('Error adding ICE candidate:', error);
                }
                break;
            
            case 'CALL_ENDED':
                this.stopWebRTC();
                this.callbacks.onCallEnded();
                break;
            
            case 'CALL_REJECTED':
                this.callbacks.onError({ type: 'CALL_REJECTED', rejectedBy: data.rejected_by });
                break;
            
            case 'ONLINE_USERS':
                console.log('Online users:', data.users);
                break;
            
            case 'ERROR':
                this.callbacks.onError(data);
                break;
        }
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected');
        }
    }
    
    disconnect() {
        this.stopWebRTC();
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Export for use in browser
if (typeof window !== 'undefined') {
    window.FaceCommsClient = FaceCommsClient;
}
