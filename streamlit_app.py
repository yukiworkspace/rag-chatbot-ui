import streamlit as st
import requests
import json
import html
import re
import os
from datetime import datetime

# セキュリティ設定
st.set_page_config(
    page_title="RAG ChatBot",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 環境変数からAPI エンドポイント取得
def get_api_endpoints():
    """環境変数からAPIエンドポイントを安全に取得"""
    try:
        auth_api = st.secrets["API_ENDPOINTS"]["AUTH_API_URL"]
        rag_api = st.secrets["API_ENDPOINTS"]["RAG_API_URL"] 
        chat_api = st.secrets["API_ENDPOINTS"]["CHAT_API_URL"]
        file_access_api = st.secrets["API_ENDPOINTS"]["FILE_ACCESS_API_URL"]
        return auth_api, rag_api, chat_api, file_access_api
    except:
        pass
    
    auth_api = os.getenv("AUTH_API_URL")
    rag_api = os.getenv("RAG_API_URL")
    chat_api = os.getenv("CHAT_API_URL")
    file_access_api = os.getenv("FILE_ACCESS_API_URL")
    
    if not auth_api or not rag_api or not chat_api:
        st.error("🔒 API エンドポイントが設定されていません。管理者に連絡してください。")
        st.info("💡 環境変数 AUTH_API_URL, RAG_API_URL, CHAT_API_URL を設定するか、Streamlit Secrets を確認してください。")
        st.stop()
    
    return auth_api, rag_api, chat_api, file_access_api

# API エンドポイント取得
AUTH_API, RAG_API, CHAT_API, FILE_ACCESS_API = get_api_endpoints()

def sanitize_input(text):
    """入力値のサニタイゼーション"""
    if not isinstance(text, str):
        return ""
    
    text = html.escape(text)
    if len(text) > 5000:
        text = text[:5000]
    
    dangerous_patterns = [
        r'<script.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe.*?</iframe>',
        r'<object.*?</object>',
        r'<embed.*?</embed>'
    ]
    
    for pattern in dangerous_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    return text.strip()

def verify_jwt_token(token):
    """JWTトークンの検証"""
    if not token:
        return None
    
    try:
        response = requests.get(
            f"{AUTH_API}/verify",
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('user_id')
        elif response.status_code == 401:
            error_data = response.json()
            if error_data.get('code') == 'TOKEN_EXPIRED':
                st.error("セッションが期限切れです。再度ログインしてください。")
            else:
                st.error("認証が無効です。再度ログインしてください。")
        return None
    except requests.exceptions.Timeout:
        st.error("認証サーバーへの接続がタイムアウトしました。")
        return None
    except Exception as e:
        st.error("認証エラーが発生しました。")
        return None

def load_chat_sessions(token):
    """チャットセッション一覧の取得"""
    try:
        response = requests.get(
            f"{CHAT_API}/sessions",
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            timeout=15
        )
        if response.status_code == 200:
            return response.json().get('sessions', [])
        return []
    except requests.exceptions.Timeout:
        st.error("セッション一覧の取得がタイムアウトしました。")
        return []
    except Exception:
        return []

def delete_chat_session(session_id, token):
    """チャットセッションの削除"""
    try:
        response = requests.delete(
            f"{CHAT_API}/sessions/{session_id}",
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            timeout=10
        )
        return response.status_code == 200
    except:
        return False

def get_file_access_url(source_uri, document_name):
    """ファイルアクセスURLを取得"""
    try:
        response = requests.post(
            f"{FILE_ACCESS_API}/get-file-url",
            headers={
                'Authorization': f'Bearer {st.session_state.auth_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            json={
                "source_uri": source_uri,
                "document_name": document_name
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('file_url')
        return None
    except Exception:
        return None
    """現在のセッションのタイトルを取得"""
    if not current_session_id:
        return "新規チャット"
    
    for session in chat_sessions:
        if session.get('session_id') == current_session_id:
            return session.get('title', '無題のチャット')
    
    return "無題のチャット"

def main():
    # URL パラメータからトークン取得
    query_params = st.experimental_get_query_params()
    token = query_params.get('token', [None])[0]
    
    # セッション状態の初期化
    if 'auth_token' not in st.session_state:
        st.session_state.auth_token = token
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'chat_sessions' not in st.session_state:
        st.session_state.chat_sessions = []
    if 'filters' not in st.session_state:
        st.session_state.filters = {}
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    
    # 認証チェック
    if not st.session_state.auth_token:
        st.error("🔒 認証が必要です。ログイン画面からアクセスしてください。")
        st.markdown("---")
        st.markdown("### セキュリティ保護されたシステムです")
        st.markdown("- 認証されたユーザーのみアクセス可能")
        st.markdown("- すべての通信は暗号化されています")
        st.markdown("- セッションは24時間で自動期限切れ")
        st.stop()
    
    user_id = verify_jwt_token(st.session_state.auth_token)
    if not user_id:
        st.session_state.auth_token = None
        st.experimental_rerun()
    
    st.session_state.user_id = user_id
    
    # 初回のセッション一覧読み込み
    if not st.session_state.chat_sessions:
        st.session_state.chat_sessions = load_chat_sessions(st.session_state.auth_token)
    
    # サイドバー：セッション管理（改善版）
    with st.sidebar:
        st.title("🤖 RAG ChatBot")
        st.write(f"👤 ユーザー: {user_id}")
        
        # セキュリティ情報表示
        with st.expander("🔒 セキュリティ情報"):
            st.write("✅ セッション暗号化済み")
            st.write("✅ データ保護有効")
            st.write("⏰ セッション有効期限: 24時間")
        
        st.divider()
        
        # 検索フィルター設定
        st.subheader("🔍 検索フィルター")
        with st.expander("詳細フィルター"):
            document_type = st.selectbox(
                "文書タイプ",
                ["", "manual", "policy", "report", "specification"],
                key="doc_type_filter"
            )
            product = st.text_input("製品名", key="product_filter", max_chars=100)
            model = st.text_input("モデル", key="model_filter", max_chars=100)
            category = st.text_input("カテゴリ", key="category_filter", max_chars=100)
            
            # 入力値のサニタイゼーション
            filters = {}
            if document_type:
                filters["document-type"] = sanitize_input(document_type)
            if product:
                filters["product"] = sanitize_input(product)
            if model:
                filters["model"] = sanitize_input(model)
            if category:
                filters["category"] = sanitize_input(category)
            
            st.session_state.filters = filters
            
            if filters:
                st.write("**適用中のフィルター:**")
                for k, v in filters.items():
                    st.write(f"• {k}: {v}")
        
        st.divider()
        
        # チャット履歴（改善版）
        st.subheader("📚 チャット履歴")
        
        # チャット管理ボタン
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 新規チャット", use_container_width=True):
                st.session_state.current_session_id = None
                st.session_state.messages = []
                st.experimental_rerun()
        
        with col2:
            if st.button("🔄 履歴更新", use_container_width=True):
                with st.spinner("セッション一覧を更新中..."):
                    st.session_state.chat_sessions = load_chat_sessions(st.session_state.auth_token)
                st.experimental_rerun()
        
        # 保存済セッション一覧（改善版）
        if st.session_state.chat_sessions:
            st.write("**保存済セッション:**")
            for session in st.session_state.chat_sessions:
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        # セッション情報のサニタイゼーション
                        session_title = sanitize_input(session.get('title', '無題のチャット'))
                        
                        # 現在選択中のセッションにはマーカーを追加
                        display_title = session_title
                        if session['session_id'] == st.session_state.current_session_id:
                            display_title = f"🔸 {session_title}"
                        
                        if st.button(
                            display_title,
                            key=f"load_{session['session_id']}",
                            use_container_width=True
                        ):
                            st.session_state.current_session_id = session['session_id']
                            # メッセージのサニタイゼーション
                            sanitized_messages = []
                            for msg in session.get('messages', []):
                                sanitized_msg = {
                                    'role': sanitize_input(msg.get('role', '')),
                                    'content': sanitize_input(msg.get('content', '')),
                                    'timestamp': msg.get('timestamp', ''),
                                    'citations': [sanitize_input(c) for c in msg.get('citations', [])],
                                    'source_documents': msg.get('source_documents', [])
                                }
                                sanitized_messages.append(sanitized_msg)
                            st.session_state.messages = sanitized_messages
                            st.experimental_rerun()
                    
                    with col2:
                        if st.button("🗑️", key=f"delete_{session['session_id']}"):
                            if delete_chat_session(session['session_id'], st.session_state.auth_token):
                                st.success("セッションを削除しました")
                                st.session_state.chat_sessions = load_chat_sessions(st.session_state.auth_token)
                                # 削除したセッションが現在のセッションの場合、新規チャットに切り替え
                                if session['session_id'] == st.session_state.current_session_id:
                                    st.session_state.current_session_id = None
                                    st.session_state.messages = []
                                st.experimental_rerun()
                            else:
                                st.error("削除に失敗しました")
        
        st.divider()
        
        # ログアウト
        if st.button("🚪 ログアウト", use_container_width=True):
            st.session_state.auth_token = None
            st.session_state.user_id = None
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.session_state.chat_sessions = []
            st.success("ログアウトしました")
            st.experimental_rerun()
    
    # メインチャット画面（改善版）
    # 現在のセッションタイトルを取得
    current_title = get_current_session_title(st.session_state.current_session_id, st.session_state.chat_sessions)
    
    # 動的タイトル表示
    st.title("🤖 RAG ChatBot")
    st.caption("セキュアな知識ベース検索システム")
    
    # セッションタイトル表示（改善版）
    if st.session_state.current_session_id:
        st.header(f"💬 {current_title}")
    else:
        st.header("💬 新規チャット")
    
    # フィルター表示
    if st.session_state.filters:
        with st.expander("🔍 検索フィルターが適用されています", expanded=False):
            for k, v in st.session_state.filters.items():
                st.write(f"**{k}**: {v}")
    
    # チャット履歴表示（永続化対応）
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            # メッセージ内容の表示（既にサニタイズ済み）
            st.markdown(message["content"])
            
            # 引用情報の表示（永続化対応・st.link_button版）
            if message["role"] == "assistant" and message.get("citations"):
                # ユニークなキーを使用して状態を永続化
                expander_key = f"citations_{i}_{st.session_state.current_session_id}"
                
                with st.expander("📚 参照文書", expanded=False, key=expander_key):
                    source_docs = message.get("source_documents", [])
                    for j, citation in enumerate(message["citations"], 1):
                        col1, col2 = st.columns([4, 1])
                        
                        with col1:
                            # 対応する文書の情報を取得
                            doc_info = source_docs[j-1] if j-1 < len(source_docs) else {}
                            source_uri = doc_info.get('source_uri', '')
                            document_name = doc_info.get('document_name', citation.replace('📄 ', ''))
                            
                            # st.link_buttonを使用（推奨）
                            if source_uri:
                                # まずファイルURLを取得
                                file_url = get_file_access_url(source_uri, document_name)
                                if file_url:
                                    st.link_button(
                                        f"📄 {document_name}",
                                        file_url,
                                        help="クリックしてファイルを新しいタブで開く"
                                    )
                                else:
                                    st.write(f"📄 {document_name} (アクセス不可)")
                            else:
                                st.write(citation)
                        
                        with col2:
                            # 関連度表示
                            score = doc_info.get('score', 0) if j-1 < len(source_docs) else 0
                            if score > 0:
                                st.metric("関連度", f"{score:.3f}", help="検索クエリとの関連度スコア")
            
            # タイムスタンプ
            if message.get("timestamp"):
                st.caption(f"🕒 {message['timestamp'][:19].replace('T', ' ')}")
    
    # ユーザー入力
    if prompt := st.chat_input("質問を入力してください（最大5000文字）"):
        # 入力値のサニタイゼーション
        sanitized_prompt = sanitize_input(prompt)
        
        # 入力値検証
        if not sanitized_prompt:
            st.error("有効な質問を入力してください。")
            st.stop()
        
        if len(sanitized_prompt) > 5000:
            st.error("質問が長すぎます（最大5000文字）。")
            st.stop()
        
        # ユーザーメッセージ表示
        with st.chat_message("user"):
            st.markdown(sanitized_prompt)
        
        # RAG APIコール
        with st.chat_message("assistant"):
            with st.spinner("🤖 AI回答を生成中..."):
                response_data = call_rag_api(
                    sanitized_prompt, 
                    st.session_state.auth_token,
                    st.session_state.current_session_id,
                    st.session_state.filters
                )
                
                if response_data.get("error"):
                    st.error(f"❌ エラー: {response_data['error']}")
                else:
                    # 回答表示
                    reply = response_data.get("reply", "回答を取得できませんでした")
                    st.markdown(reply)
                    
                    # 新規セッションの場合、セッションIDを更新
                    if response_data.get("is_new_session"):
                        st.session_state.current_session_id = response_data["session_id"]
                        session_title = response_data.get('title', '無題')
                        st.success(f"✨ 新しいセッション「{session_title}」を開始しました")
                    
                    # 引用情報表示
                    citations = response_data.get("citations", [])
                    source_docs = response_data.get("source_documents", [])
                    
                    if citations:
                        with st.expander("📚 参照文書"):
                            for j, citation in enumerate(citations, 1):
                                col1, col2 = st.columns([4, 1])
                                
                                with col1:
                                    # 対応する文書の情報を取得
                                    doc_info = source_docs[j-1] if j-1 < len(source_docs) else {}
                                    source_uri = doc_info.get('source_uri', '')
                                    document_name = doc_info.get('document_name', citation.replace('📄 ', ''))
                                    
                                    # st.link_buttonを使用（推奨）
                                    if source_uri:
                                        # まずファイルURLを取得
                                        file_url = get_file_access_url(source_uri, document_name)
                                        if file_url:
                                            st.link_button(
                                                f"📄 {document_name}",
                                                file_url,
                                                help="クリックしてファイルを新しいタブで開く"
                                            )
                                        else:
                                            st.write(f"📄 {document_name} (アクセス不可)")
                                    else:
                                        st.write(citation)
                                
                                with col2:
                                    # 関連度表示
                                    score = doc_info.get('score', 0) if j-1 < len(source_docs) else 0
                                    if score > 0:
                                        st.metric("関連度", f"{score:.3f}", help="検索クエリとの関連度スコア")
        
        # セッション一覧を更新（新規セッション作成時）
        if response_data.get("is_new_session"):
            st.session_state.chat_sessions = load_chat_sessions(st.session_state.auth_token)
        
        st.experimental_rerun()

def call_rag_api(query, token, session_id, filters):
    """RAG APIの呼び出し（セキュリティ対策付き）"""
    try:
        # リクエストペイロードの構築
        payload = {
            "message": query,
            "filters": filters
        }
        
        if session_id:
            payload["session_id"] = session_id
        
        # APIリクエスト実行
        response = requests.post(
            f"{RAG_API}/query",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'User-Agent': 'RAG-ChatBot/1.0'
            },
            json=payload,
            timeout=180,  # 3分タイムアウト
            verify=True   # SSL証明書検証
        )
        
        # レスポンス処理
        if response.status_code == 200:
            response_data = response.json()
            
            # レスポンスデータのサニタイゼーション
            if 'reply' in response_data:
                response_data['reply'] = sanitize_input(response_data['reply'])
            
            if 'citations' in response_data:
                sanitized_citations = []
                for citation in response_data['citations']:
                    sanitized_citations.append(sanitize_input(citation))
                response_data['citations'] = sanitized_citations
            
            return response_data
        
        elif response.status_code == 401:
            return {"error": "認証が無効です。再度ログインしてください。"}
        elif response.status_code == 403:
            return {"error": "アクセス権限がありません。"}
        elif response.status_code == 429:
            return {"error": "リクエストが多すぎます。しばらく待ってから再試行してください。"}
        else:
            return {"error": f"APIエラー（ステータス: {response.status_code}）"}
            
    except requests.exceptions.Timeout:
        return {"error": "⏰ 回答の生成に時間がかかりすぎました。もう一度お試しください。"}
    except requests.exceptions.SSLError:
        return {"error": "🔒 SSL証明書エラーが発生しました。"}
    except requests.exceptions.ConnectionError:
        return {"error": "🌐 ネットワーク接続エラーが発生しました。"}
    except Exception as e:
        return {"error": "❌ 予期しないエラーが発生しました。"}

if __name__ == "__main__":
    main()
