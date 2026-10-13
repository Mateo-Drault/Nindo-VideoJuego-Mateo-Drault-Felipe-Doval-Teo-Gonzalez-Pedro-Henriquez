namespace Nindo
{
    public partial class UIManager
    {
        /// <summary>
        /// ¿Está a la vista este consejo (el texto crudo, con las teclas entre llaves)? Quien abre un consejo y lo cierra
        /// solo lo cierra si sigue siendo el suyo: si en el medio salió otro, HideTutorial escondía el ajeno.
        /// </summary>
        public bool TutorialShowing(string raw) => tutorialVisible && tutorialRaw == raw;
    }
}
