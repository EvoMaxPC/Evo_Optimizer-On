using System.Windows;
using System.Windows.Controls;
using Evo.Core.System;
using Evo.Testing;
using Evo.Windows;

namespace Evo.App;

/// <summary>Ventana principal. Conecta la vista con MainViewModel.</summary>
public partial class MainWindow : Window
{
    private readonly MainViewModel _viewModel;

    public MainWindow()
    {
        InitializeComponent();

        // En producción usamos los accesorios reales de Windows.
        // El manifiesto de la aplicación declara requireAdministrator para
        // capacidades con privilegio Admin (desviación documentada).
        var environment = new WindowsSystemEnvironment();
        var registry = new WindowsRegistryAccessor();
        var confirmations = new WpfConfirmationProvider();
        var restorePoints = new WpfRestorePointService();
        var commands = new WpfCommandRunner();

        _viewModel = MainViewModel.Create(environment, registry, confirmations, restorePoints, commands);

        DataContext = _viewModel;

        StatusText.Text = _viewModel.IsWindowsCompatible
            ? "Windows compatible — se pueden aplicar capacidades."
            : _viewModel.CompatibilityMessage;
        BuildText.Text = $"Build {_viewModel.CurrentBuild}  UBR {_viewModel.UBR}";
        EditionText.Text = $"Edición: {_viewModel.EditionID}  Tipo: {_viewModel.InstallationType}";

        SectionsList.ItemsSource = _viewModel.Sections;
    }

    private void Simulate_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && button.DataContext is CapabilityViewModel capability)
        {
            _viewModel.Simulate(capability);
            RefreshResults();
        }
    }

    private void Apply_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && button.DataContext is CapabilityViewModel capability)
        {
            _viewModel.Apply(capability);
            RefreshResults();
        }
    }

    private void Undo_Click(object sender, RoutedEventArgs e)
    {
        _viewModel.Undo();
        RefreshResults();
    }

    private void RefreshResults()
    {
        ResultsText.Text = _viewModel.ResultsText;
    }
}
