from typing import Callable


def modify_sentence(sentence: str, update_word_callback: Callable[[str], str]) -> str:
    words = sentence.split()
    stripped_words = [word.lstrip(";,'\"()[]{}").rstrip(";,'\".?!:") for word in words]
    modified_words = [update_word_callback(word) for word in stripped_words]
    words = [word.replace(stripped_words[index], modified_words[index]) for index, word in enumerate(words) if word]
    return " ".join(words)
