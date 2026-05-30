import streamlit as st
import whisper
import json
import os
from google import genai
from google.genai import types

# ----------------------------------------------------
# 設定：GeminiのAPIキー（お使いのキーに変えてください）
# ----------------------------------------------------
API_KEY = st.secrets["GEMINI_API_KEY"]

# ----------------------------------------------------
# 画面のデザイン
# ----------------------------------------------------
st.set_page_config(page_title="super ball company", page_icon="🎙️")
st.title("超球形社 クイズアプリ")
st.write("M4Aなどの音声ファイルをアップロードすると、AIが文字起こしをして4択クイズを自動作成します。")

# アプリの「記憶（セッション状態）」を初期化
if "step" not in st.session_state:
    st.session_state.step = "start"  # start -> quiz -> finish
    st.session_state.transcribed_text = ""
    st.session_state.quiz_data = []
    st.session_state.score = 0
    st.session_state.user_answers = {}

# ----------------------------------------------------
# ステップ1：ファイルアップロードと文字起こし
# ----------------------------------------------------
if st.session_state.step == "start":
    st.subheader("1. 音声ファイルのアップロード")
    
    # M4A, MP3, WAV形式のファイルを受け付ける
    uploaded_file = st.file_uploader(
        "音声ファイルを選択するか、ここにドラッグ＆ドロップしてください", 
        type=["m4a", "mp3", "wav"]
    )
    
    if uploaded_file is not None:
        # 画面上で音声が再生できるようにする
        st.audio(uploaded_file, format="audio/m4a")
        
        if st.button("文字起こし＆クイズ作成を開始", type="primary"):
            
            # アップロードされたファイルを一時的にパソコンに保存する処理
            # (Whisperにファイルを読み込ませるために必要です)
            temp_filename = "temp_uploaded_audio.m4a"
            with open(temp_filename, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            with st.spinner("Whisperが音声を解析中... (数分かかる場合があります)"):
                try:
                    model = whisper.load_model("tiny")
                    # 一時保存したファイルを読み込む
                    result = model.transcribe(
                        temp_filename, 
                        language="ja",
                        initial_prompt="これは大学時代のサークル仲間2人によるポッドキャストの対談です。ジェロニモと、かいがビジネスや創作活動に関するトークをしています。世に出る、などの言葉が含まれます。ゼロはジェロです。会はかいです"
                    )
                    st.session_state.transcribed_text = result["text"]
                except Exception as e:
                    st.error(f"文字起こし中にエラーが発生しました: {e}")
                finally:
                    # 使い終わった一時ファイルを削除
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
                        
            with st.spinner("Geminiがクイズを自動生成中..."):
                # Geminiでクイズ作成
                client = genai.Client(api_key=API_KEY)
                prompt = f"""
                以下の文字起こしテキストの内容に基づいて、4択クイズを2問作成してください。
                【文字起こしテキスト】
                {st.session_state.transcribed_text}
                【出力ルール】
                必ず以下の構造のJSON形式だけで出力してください。余計な解説文や挨拶は含めないでください。
                [
                  {{
                    "question": "問題文",
                    "choices": {{"A": "選択肢1", "B": "選択肢2", "C": "選択肢3", "D": "選択肢4"}},
                    "correct_answer": "AまたはBまたはCまたはD",
                    "explanation": "解説"
                  }}
                ]
                """
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                
                # クイズデータを記憶して次の画面へ
                st.session_state.quiz_data = json.loads(response.text)
                st.session_state.step = "quiz"
                st.rerun()

# ----------------------------------------------------
# ステップ2：クイズ出題画面
# ----------------------------------------------------
elif st.session_state.step == "quiz":
    st.subheader("🎯 クイズに挑戦！")
    
    with st.expander("📝 文字起こしされたテキストを確認する"):
        st.write(st.session_state.transcribed_text)
        
    with st.form("quiz_form"):
        for i, item in enumerate(st.session_state.quiz_data, 1):
            st.markdown(f"### **第{i}問: {item['question']}**")
            options = [f"{key}: {value}" for key, value in item['choices'].items()]
            
            ans = st.radio(
                "選択肢を選んでください", 
                options, 
                key=f"q_{i}"
            )
            st.session_state.user_answers[i] = ans.split(":")[0]
            st.write("---")
            
        submitted = st.form_submit_button("回答を送信して採点！", type="primary")
        if submitted:
            score = 0
            for i, item in enumerate(st.session_state.quiz_data, 1):
                if st.session_state.user_answers[i] == item['correct_answer']:
                    score += 1
            st.session_state.score = score
            st.session_state.step = "finish"
            st.rerun()

# ----------------------------------------------------
# ステップ3：結果発表画面
# ----------------------------------------------------
elif st.session_state.step == "finish":
    st.subheader("🏁 結果発表")
    total_q = len(st.session_state.quiz_data)
    
    st.metric(label="あなたのスコア", value=f"{total_q}問中 {st.session_state.score}問 正解！")
    
    st.write("### 💡 答え合わせと解説")
    for i, item in enumerate(st.session_state.quiz_data, 1):
        user_ans = st.session_state.user_answers[i]
        correct_ans = item['correct_answer']
        
        st.markdown(f"#### **第{i}問: {item['question']}**")
        st.write(f"あなたの回答: **{user_ans}**")
        st.write(f"正解: **{correct_ans}**")
        
        if user_ans == correct_ans:
            st.success("🟢 正解です！")
        else:
            st.error("❌ 残念、不正解です。")
            
        st.info(f"**解説:** {item['explanation']}")
        st.write("---")
        
    if st.button("別のファイルで試す（最初に戻る）"):
        st.session_state.step = "start"
        st.session_state.user_answers = {}
        st.session_state.score = 0
        st.rerun()
